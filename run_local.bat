@echo off
chcp 65001 >nul
cd /d "%~dp0"
set DJANGO_SETTINGS_MODULE=core.settings
set DJANGO_DEBUG=True
if not exist .venv (
  echo Первый запуск: ставлю зависимости...
  python -m venv .venv
  .venv\Scripts\python -m pip install -q -r requirements.txt pillow
)
.venv\Scripts\python manage.py makemigrations accounts corpus suggestions gamification editor clips reading -v0
.venv\Scripts\python manage.py migrate -v0
echo.
echo  Пользователь: http://127.0.0.1:8000/clips/        (user1 / user12345)
echo  Редактор:     http://127.0.0.1:8000/clips/review/ (admin / admin12345)
echo  Закрой это окно, чтобы остановить сайт.
echo.
start "" http://127.0.0.1:8000/
.venv\Scripts\python manage.py runserver 127.0.0.1:8000
