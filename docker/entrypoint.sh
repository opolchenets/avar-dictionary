#!/bin/sh
set -o errexit
set -o nounset
set -o pipefail

if [ -n "${POSTGRES_HOST:-}" ]; then
  echo "Waiting for PostgreSQL at ${POSTGRES_HOST}:${POSTGRES_PORT:-5432}..."
  while ! python - <<'PY'
import os
import psycopg2
from psycopg2 import OperationalError

try:
    psycopg2.connect(
        dbname=os.getenv("POSTGRES_DB", "avar_dictionary"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT", "5432"),
    ).close()
except OperationalError as exc:  # pragma: no cover - diagnostics only
    raise SystemExit(f"Database not ready: {exc}")
PY
  do
    sleep 1
  done
  echo "PostgreSQL is available"
fi

python manage.py makemigrations

echo "Applying database migrations"
python manage.py migrate --noinput

echo "Seeding initial corpus data"
python manage.py seed_initial_data

echo "Collecting static files"
python manage.py collectstatic --noinput

echo "Starting Gunicorn"
exec gunicorn core.wsgi:application --bind 0.0.0.0:8000 --workers ${GUNICORN_WORKERS:-3}
