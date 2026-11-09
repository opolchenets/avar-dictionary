#!/bin/bash
# Ежедневный бэкап: дамп PostgreSQL + архив media. Хранит последние 14 дней.
# cron: 30 3 * * * /opt/avar/deploy/backup.sh >> /var/log/avar-backup.log 2>&1
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${BACKUP_DIR:-/root/backups}"
STAMP="$(date +%Y-%m-%d_%H%M)"
mkdir -p "$DEST"
cd "$APP_DIR"
set -a; . ./.env; set +a
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" | gzip > "$DEST/db_$STAMP.sql.gz"
tar -czf "$DEST/media_$STAMP.tar.gz" media
find "$DEST" -type f -mtime +14 -delete
echo "$STAMP backup ok: $(du -sh "$DEST" | cut -f1)"
