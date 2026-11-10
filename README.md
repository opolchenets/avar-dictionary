# Авар МацӀ — сбор аварского корпуса

Django-сайт исправления расшифровок и записи фраз. Каждая отправленная работа ждёт решения редактора. Сравнение ответов и проверка по эталону дают только предварительную подсказку. Только редактор принимает или отклоняет работу; в рейтинг входят принятые им работы. Для озвучки доступны принятие, переозвучка и отклонение.

## Локальный запуск

PowerShell, существующее окружение Anaconda base:

```powershell
conda activate base
Set-Location -LiteralPath "C:\Users\Grinblast Georald\OneDrive\Рабочий стол\авар\site\avar-test"
python manage.py site_preflight
python manage.py check
python manage.py migrate --check
python manage.py runserver 127.0.0.1:8000
```

Открыть http://127.0.0.1:8000/. Код, db.sqlite3 и media должны принадлежать одному экземпляру. Код из GitHub не содержит рабочую базу и аудио.

## Сервер

Порядок — [deploy/README.md](deploy/README.md). Основной файл — docker-compose.production.yml. Caddy открывается профилем public после переноса данных и смены тестовых паролей. FFmpeg устанавливается в серверный образ, существующая Anaconda не меняется.

## Проверки

```powershell
python manage.py test --noinput
python manage.py makemigrations --check --dry-run
```

Миграции приложений хранятся в Git. При старте только migrate; не создавать миграции автоматически для починки неизвестной базы.

## Данные

instance_transfer export DIRECTORY — база и media с контрольными суммами; записи на время экспорта остановить.
instance_transfer import DIRECTORY — только в пустой подготовленный экземпляр.
export_corpus DIRECTORY — CSV принятых расшифровок, эталонов и озвучек без учётных данных.

База, записи участников, пакеты переноса и секреты не публикуются в репозитории.
