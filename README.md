# ERP nội bộ công ty ABC (Docker)
Flask + PostgreSQL + Nginx (HTTP). Chạy: `cp .env.example .env && nano .env && sudo mkdir -p /srv/erp/pgdata && docker compose up -d --build`
Mở `http://IP-máy-chủ`, đăng nhập bằng ADMIN_USERNAME / ADMIN_PASSWORD trong `.env`.
- Bật đồng bộ AWS: điền AWS_API_URL, AWS_API_KEY rồi `docker compose --profile sync up -d`
- Backup: `./scripts/backup.sh`
- Cập nhật code: `git pull && docker compose up -d --build`
- Dữ liệu DB nằm ở PGDATA_DIR; `docker compose down` giữ dữ liệu, KHÔNG dùng `down -v` và đừng xóa thư mục pgdata.
