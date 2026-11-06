import os
from datetime import timedelta
from functools import wraps
import psycopg2, psycopg2.extras
from flask import Flask, g, render_template, request, redirect, url_for, session, flash, abort
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from db import connect

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ["SECRET_KEY"],
    SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8))
CSRFProtect(app)

@app.template_filter("vnd")
def vnd(v): return "{:,.0f}".format(v or 0).replace(",", ".") + " ₫"
@app.template_filter("d")
def fd(v): return v.strftime("%d/%m/%Y") if v else "—"
@app.template_filter("dt")
def fdt(v): return v.strftime("%d/%m/%Y %H:%M") if v else "—"

# ---------- DB ----------
def db():
    if "db" not in g: g.db = connect()
    return g.db

@app.teardown_appcontext
def close_db(_):
    c = g.pop("db", None)
    if c: c.close()

def qall(sql, args=()):
    with db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as c:
        c.execute(sql, args); rows = c.fetchall()
    db().rollback(); return rows

def q1(sql, args=()):
    r = qall(sql, args); return r[0] if r else None

def run(sql, args=()):
    try:
        with db().cursor() as c: c.execute(sql, args)
        db().commit(); return True
    except psycopg2.Error as e:
        db().rollback()
        flash("Không lưu được: trùng username/email hoặc dữ liệu không hợp lệ.", "error")
        return False

# ---------- Auth ----------
def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if "uid" not in session: return redirect(url_for("login"))
        return f(*a, **k)
    return w

def admin_required(f):
    @wraps(f)
    @login_required
    def w(*a, **k):
        if session.get("role") != "admin": abort(403)
        return f(*a, **k)
    return w

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = q1("SELECT * FROM employees WHERE username=%s AND is_active", (request.form["username"].strip(),))
        if u and check_password_hash(u["password_hash"], request.form["password"]):
            session.clear(); session.permanent = True
            session.update(uid=u["id"], username=u["username"], role=u["role"], name=u["full_name"])
            return redirect(url_for("profile"))
        flash("Sai tên đăng nhập hoặc mật khẩu", "error")
    return render_template("login.html")

@app.route("/logout", methods=["POST"])
def logout():
    session.clear(); return redirect(url_for("login"))

# ---------- Nhân viên ----------
@app.route("/")
@login_required
def profile():
    e = q1("SELECT * FROM employees WHERE id=%s", (session["uid"],))
    if not e: session.clear(); return redirect(url_for("login"))
    return render_template("profile.html", e=e, page="profile")

@app.route("/feedback")
@login_required
def feedback():
    page = max(request.args.get("page", 1, type=int), 1)
    kw = request.args.get("q", "").strip(); per = 15
    like = f"%{kw}%"
    where = "WHERE full_name ILIKE %s OR email ILIKE %s OR phone ILIKE %s OR message ILIKE %s" if kw else ""
    args = (like,) * 4 if kw else ()
    rows = qall(f"SELECT * FROM customer_feedback {where} ORDER BY created_at_aws DESC LIMIT %s OFFSET %s",
                args + (per, (page - 1) * per))
    total = q1(f"SELECT count(*) AS c FROM customer_feedback {where}", args)["c"]
    return render_template("feedback.html", rows=rows, page_no=page, total=total, kw=kw,
                           has_next=page * per < total, page="feedback")

# ---------- Admin ----------
def read_form():
    f = request.form
    try: salary = max(int(f.get("salary") or 0), 0)
    except ValueError: salary = 0
    return dict(username=f["username"].strip(), full_name=f["full_name"].strip(),
                date_of_birth=f.get("date_of_birth") or None, phone=f.get("phone", "").strip(),
                email=f.get("email", "").strip() or None, salary=salary,
                role="admin" if f.get("role") == "admin" else "employee", is_active="is_active" in f)

@app.route("/admin/employees")
@admin_required
def employees():
    kw = request.args.get("q", "").strip()
    rows = qall("SELECT * FROM employees WHERE %s='' OR full_name ILIKE %s OR username ILIKE %s OR email ILIKE %s ORDER BY id",
                (kw, f"%{kw}%", f"%{kw}%", f"%{kw}%"))
    return render_template("employees.html", rows=rows, kw=kw, page="employees")

@app.route("/admin/employees/new", methods=["GET", "POST"])
@admin_required
def employee_new():
    if request.method == "POST":
        d = read_form(); pw = request.form.get("password", "")
        if len(pw) < 8: flash("Mật khẩu tối thiểu 8 ký tự", "error")
        else:
            d["ph"] = generate_password_hash(pw)
            if run("""INSERT INTO employees(username,password_hash,role,full_name,date_of_birth,phone,email,salary,is_active)
                      VALUES(%(username)s,%(ph)s,%(role)s,%(full_name)s,%(date_of_birth)s,%(phone)s,%(email)s,%(salary)s,%(is_active)s)""", d):
                flash("Đã thêm nhân viên", "ok"); return redirect(url_for("employees"))
    return render_template("employee_form.html", e=None, page="employees")

@app.route("/admin/employees/<int:eid>/edit", methods=["GET", "POST"])
@admin_required
def employee_edit(eid):
    e = q1("SELECT * FROM employees WHERE id=%s", (eid,))
    if not e: abort(404)
    if request.method == "POST":
        d = read_form(); d["id"] = eid; pw = request.form.get("password", "")
        if pw and len(pw) < 8: flash("Mật khẩu mới tối thiểu 8 ký tự", "error")
        else:
            if eid == session["uid"]: d["role"], d["is_active"] = "admin", True   # không tự khóa/hạ quyền mình
            ok = run("""UPDATE employees SET username=%(username)s, full_name=%(full_name)s, date_of_birth=%(date_of_birth)s,
                        phone=%(phone)s, email=%(email)s, salary=%(salary)s, role=%(role)s, is_active=%(is_active)s,
                        updated_at=now() WHERE id=%(id)s""", d)
            if ok and pw: run("UPDATE employees SET password_hash=%s WHERE id=%s", (generate_password_hash(pw), eid))
            if ok: flash("Đã cập nhật", "ok"); return redirect(url_for("employees"))
    return render_template("employee_form.html", e=e, page="employees")

@app.route("/admin/employees/<int:eid>/delete", methods=["POST"])
@admin_required
def employee_delete(eid):
    if eid == session["uid"]: flash("Không thể tự xóa tài khoản của mình", "error")
    elif run("DELETE FROM employees WHERE id=%s", (eid,)): flash("Đã xóa nhân viên", "ok")
    return redirect(url_for("employees"))

@app.errorhandler(403)
@app.errorhandler(404)
def err(e):
    return render_template("error.html", code=e.code, msg="Bạn không có quyền truy cập" if e.code == 403 else "Không tìm thấy trang"), e.code
