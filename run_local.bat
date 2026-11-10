@echo off
chcp 65001 >nul
cd /d "%~dp0"
call conda activate base
if errorlevel 1 exit /b 1
python tools\verify_local.py
if errorlevel 1 exit /b 1
python manage.py check
if errorlevel 1 exit /b 1
python manage.py migrate --check
if errorlevel 1 exit /b 1
python manage.py runserver 127.0.0.1:8000
