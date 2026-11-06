#!/usr/bin/env bash
# Backup DB ra file .sql.gz. Dùng: ./scripts/backup.sh   (cron: 0 2 * * * /opt/erp/scripts/backup.sh)
set -e
cd "$(dirname "$0")/.."
source .env
mkdir -p backups
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "backups/erp_$(date +%F_%H%M).sql.gz"
find backups -name '*.sql.gz' -mtime +14 -delete
