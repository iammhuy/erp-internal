"""Kéo feedback từ API AWS về DB nội bộ (cursor theo updated_at,id). Bật bằng: docker compose --profile sync up -d"""
import os, time, logging, requests
from psycopg2.extras import execute_values
from db import connect

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
API, KEY = os.getenv("AWS_API_URL", ""), os.getenv("AWS_API_KEY", "")
INTERVAL, BATCH = int(os.getenv("SYNC_INTERVAL", "20")), 500

UPSERT = """INSERT INTO customer_feedback(aws_id,full_name,phone,email,message,created_at_aws,updated_at_aws)
VALUES %s ON CONFLICT (aws_id) DO UPDATE SET full_name=EXCLUDED.full_name, phone=EXCLUDED.phone,
email=EXCLUDED.email, message=EXCLUDED.message, updated_at_aws=EXCLUDED.updated_at_aws, synced_at=now()"""

def sync_once(conn, http):
    with conn.cursor() as cur:
        cur.execute("SELECT last_ts,last_id FROM sync_state WHERE name='feedback'")
        ts, last_id = cur.fetchone()
    conn.rollback()
    r = http.get(API, timeout=15, headers={"Authorization": f"Bearer {KEY}"},
                 params={"after_ts": ts.isoformat(), "after_id": last_id, "limit": BATCH})
    r.raise_for_status()
    items = r.json()["items"]
    if not items:
        return 0
    rows = [(i["id"], i["full_name"], i["phone"], i["email"], i["message"], i["created_at"], i["updated_at"]) for i in items]
    with conn, conn.cursor() as cur:
        execute_values(cur, UPSERT, rows)
        cur.execute("UPDATE sync_state SET last_ts=%s,last_id=%s,last_run=now() WHERE name='feedback'",
                    (items[-1]["updated_at"], items[-1]["id"]))
    return len(items)

def main():
    if not API:
        logging.warning("AWS_API_URL trống, sync không chạy. Điền .env rồi restart.")
        time.sleep(10**9)
    http, conn, wait = requests.Session(), connect(), INTERVAL
    while True:
        try:
            if conn.closed: conn = connect()
            n = sync_once(conn, http)
            if n: logging.info("Đã đồng bộ %d bản ghi", n)
            wait = INTERVAL
            if n >= BATCH: continue
        except Exception as e:
            logging.warning("Sync lỗi: %s", e)
            wait = min(wait * 2, 300)
        time.sleep(wait)

if __name__ == "__main__":
    main()
