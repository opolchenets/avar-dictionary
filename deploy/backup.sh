#!/bin/bash
set -euo pipefail
umask 077
cd "$(dirname "$0")/.."
DEST="${BACKUP_DIR:-/root/backups/avar}"
mkdir -p "$DEST"
WORK=$(mktemp -d "$DEST/.avar-backup.XXXXXX")
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
cleanup() {
    docker compose -f docker-compose.production.yml start web >/dev/null || true
    rm -f -- "$WORK/database.sql" "$WORK/media.tar.gz" "$WORK/SHA256SUMS"
    rmdir -- "$WORK" 2>/dev/null || true
}
trap cleanup EXIT
# Freeze application writes so DB and uploaded files represent the same state.
docker compose -f docker-compose.production.yml stop web
docker compose -f docker-compose.production.yml exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-acl' > "$WORK/database.sql"
tar -czf "$WORK/media.tar.gz" media
(cd "$WORK" && sha256sum database.sql media.tar.gz > SHA256SUMS)
tar -czf "$DEST/avar_$STAMP.tar.gz.part" -C "$WORK" database.sql media.tar.gz SHA256SUMS
mv -- "$DEST/avar_$STAMP.tar.gz.part" "$DEST/avar_$STAMP.tar.gz"
find "$DEST" -maxdepth 1 -type f -name 'avar_????????T??????Z.tar.gz' -mtime +14 -delete
echo "Backup completed: $DEST/avar_$STAMP.tar.gz"
