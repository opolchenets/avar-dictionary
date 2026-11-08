#!/usr/bin/env bash
# Локальный запуск сайта (Linux / macOS). Аналог run_local.bat.
set -e
cd "$(dirname "$0")"
export DJANGO_SETTINGS_MODULE=core.settings
export DJANGO_DEBUG=True

if [ ! -d .venv ]; then
  echo "Первый запуск: ставлю зависимости..."
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt pillow
fi

# миграции в репозитории не хранятся — создаём и применяем
.venv/bin/python manage.py makemigrations accounts corpus suggestions gamification editor clips reading -v0
.venv/bin/python manage.py migrate -v0

echo
echo "  Сайт:      http://127.0.0.1:8000/"
echo "  Редактор:  http://127.0.0.1:8000/clips/review/"
echo "  Остановить: Ctrl+C"
echo
.venv/bin/python manage.py runserver 127.0.0.1:8000
