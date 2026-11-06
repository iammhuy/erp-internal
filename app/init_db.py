"""Tạo bảng (nếu chưa có) và admin đầu tiên. Chạy mỗi lần web khởi động, an toàn khi chạy lặp."""
import os, time
import psycopg2
from werkzeug.security import generate_password_hash
from db import connect

SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
  id SERIAL PRIMARY KEY,
  username VARCHAR(50) UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role VARCHAR(10) NOT NULL DEFAULT 'employee' CHECK (role IN ('admin','employee')),
  full_name VARCHAR(100) NOT NULL,
  date_of_birth DATE,
  phone VARCHAR(20),
  email VARCHAR(100) UNIQUE,
  salary NUMERIC(14,0) NOT NULL DEFAULT 0,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS customer_feedback (
  id BIGSERIAL PRIMARY KEY,
  aws_id BIGINT UNIQUE NOT NULL,
  full_name VARCHAR(100), phone VARCHAR(20), email VARCHAR(100), message TEXT,
  created_at_aws TIMESTAMPTZ NOT NULL,
  updated_at_aws TIMESTAMPTZ NOT NULL,
  synced_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_fb_created ON customer_feedback (created_at_aws DESC);
CREATE TABLE IF NOT EXISTS sync_state (
  name TEXT PRIMARY KEY,
  last_ts TIMESTAMPTZ NOT NULL DEFAULT '1970-01-01 00:00+00',
  last_id BIGINT NOT NULL DEFAULT 0,
  last_run TIMESTAMPTZ
);
INSERT INTO sync_state(name) VALUES ('feedback') ON CONFLICT DO NOTHING;
"""

def main():
    for _ in range(30):
        try:
            conn = connect(); break
        except psycopg2.OperationalError:
            time.sleep(2)
    else:
        raise SystemExit("Không kết nối được DB")
    with conn, conn.cursor() as cur:
        cur.execute(SCHEMA)
        cur.execute("SELECT count(*) FROM employees")
        if cur.fetchone()[0] == 0:
            cur.execute(
                "INSERT INTO employees(username,password_hash,role,full_name,email) VALUES(%s,%s,'admin','Quản trị viên',%s)",
                (os.getenv("ADMIN_USERNAME", "admin"),
                 generate_password_hash(os.environ["ADMIN_PASSWORD"]), "admin@abc.local"))
            print("Đã tạo admin:", os.getenv("ADMIN_USERNAME", "admin"))
    print("DB sẵn sàng")

if __name__ == "__main__":
    main()
