#!/bin/bash
set -euo pipefail
if [ "${1:-}" != "--confirm-empty-target" ] || [ -z "${2:-}" ]; then
    echo "Usage on an EMPTY installation: bash deploy/restore.sh --confirm-empty-target /absolute/path/avar_TIMESTAMP.tar.gz"
    exit 1
fi
ARCHIVE=$(realpath "$2")
cd "$(dirname "$0")/.."
[ ! -d media ] || [ -z "$(ls -A media)" ] || { echo 'media must be empty'; exit 1; }
WORK=$(mktemp -d)
# Archives must come from this site's trusted backups.
tar -xzf "$ARCHIVE" -C "$WORK" database.sql media.tar.gz SHA256SUMS
(cd "$WORK" && sha256sum -c SHA256SUMS)
docker compose -f docker-compose.production.yml up -d db
docker compose -f docker-compose.production.yml stop web || true
for attempt in $(seq 1 30); do
    if docker compose -f docker-compose.production.yml exec -T db sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; then
        break
    fi
    sleep 2
done
TABLES=$(docker compose -f docker-compose.production.yml exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT count(*) FROM information_schema.tables WHERE table_schema='"'"'public'"'"';"')
[ "$TABLES" = "0" ] || { echo 'Database must be empty'; exit 1; }
docker compose -f docker-compose.production.yml exec -T db sh -c 'psql -v ON_ERROR_STOP=1 --single-transaction -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$WORK/database.sql"
tar -xzf "$WORK/media.tar.gz"
echo "Restored. Start web after checking the restored files and database. Temporary files: $WORK"
