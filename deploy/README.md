# Тестовый сервер аварского корпуса

Это единая версия кода и конфигурации. Локальный сайт — `avar-test`, Anaconda base.
Код, пакет переноса с персональными данными и `.env` хранятся отдельно. Пакет данных не помещать в Git.

## Что подготовлено

- Фиксированные миграции приложений, PostgreSQL 16, Gunicorn, Caddy и HTTPS.
- Приватные аудиофайлы: исходные клипы доступны вошедшим, записи участников — автору и редакторам.
- На сервере FFmpeg проверяет аудио и определяет длительность по декодированным отсчётам; он устанавливается только в Docker-образ.
- Пакет переноса сохраняет пользователей, пароли-хеши, районы, альянсы, исходные материалы, работы и связи.
- `site_preflight` проверяет наличие материалов и запрещает известные тестовые пароли администраторов.

## До запуска

Нужны IP сервера, SSH-доступ и домен с A-записью на этот IP. Порты 80/443 доступны снаружи, PostgreSQL и Gunicorn наружу не публикуются. SSH — по ключу; запрет паролей включать только после проверки входа по ключу. Требуется установленный Docker с Compose.

Распаковать пакет кода в `/opt/avar`. Распаковать приватный пакет данных так, чтобы в `/opt/avar/transfer/instance` лежали `database.json`, `manifest.json`, `media/`.

```bash
cd /opt/avar
cp .env.production.example .env
chmod 600 .env
```

В `.env` заменить SITE_DOMAIN, DJANGO_ALLOWED_HOSTS, DJANGO_CSRF_TRUSTED_ORIGINS, DJANGO_SECRET_KEY и POSTGRES_PASSWORD. Ключ — не менее 50 случайных символов; пример получения: `openssl rand -hex 32`. Пароль базы — другая случайная строка. Не оставлять слова REPLACE или пример домена.

## Создание базы и импорт — без публичного сайта

Caddy запускается только с профилем `public`, поэтому данные и пароли можно подготовить до открытия сайта.

```bash
cd /opt/avar
mkdir -p media transfer
docker compose -f docker-compose.production.yml build web
docker compose -f docker-compose.production.yml up -d db
docker compose -f docker-compose.production.yml run --rm web python manage.py migrate --noinput
docker compose -f docker-compose.production.yml run --rm web python manage.py instance_transfer import /app/transfer/instance
docker compose -f docker-compose.production.yml run --rm web python manage.py changepassword admin
docker compose -f docker-compose.production.yml run --rm web python manage.py site_preflight --production
docker compose -f docker-compose.production.yml run --rm web python manage.py check --deploy --fail-level WARNING
docker compose -f docker-compose.production.yml run --rm web python manage.py test --noinput
```

Импорт откажется перезаписывать существующую базу/медиа. Повторный запуск после успешного импорта не требуется. Ожидаемые исходные количества указаны в manifest.json. В имеющемся пакете: 883 клипа, 80 текстов, 2 записи, 5 пользователей. Перед публичным тестом проверить список пользователей в админке: аккаунты для тестов отключить, реальные роли сохранить. Ничего не удалять массовой командой без отдельного решения.

## Открыть сайт

```bash
cd /opt/avar
docker compose -f docker-compose.production.yml --profile public up -d
docker compose -f docker-compose.production.yml logs --tail=100 web caddy
```

Открыть `https://ВАШ-ДОМЕН/`. Проверить вход и выход, обычного участника и редактора, звук, запись с микрофона и отправку с компьютера/телефона. Адрес по HTTP должен переводить на HTTPS.

Два разных участника: одинаковые правки принимаются, разные попадают редактору; новая запись появляется в очереди. Проверить принять/переозвучить/отклонить, повторную отправку при временной потере связи и сохранность результатов после `docker compose -f docker-compose.production.yml restart web`.

Прямая ссылка на аудио без входа должна отправлять на login. Другой обычный участник не должен получать чужую запись. Страницы редактора и админки обычному участнику недоступны.

Настоящие микрофон, HTTPS, PostgreSQL, Docker и Caddy проверяются только после появления сервера. Успех локальных тестов не заменяет эти проверки.

## Бэкап и восстановление

```bash
cd /opt/avar
bash deploy/backup.sh
```

Скрипт кратковременно останавливает web, сохраняет согласованные PostgreSQL + media с контрольными суммами, затем запускает web. Копии — `/root/backups/avar/`; хранение 14 дней только собственных архивов. Планировщик root:

```cron
30 3 * * * /bin/bash /opt/avar/deploy/backup.sh >> /var/log/avar-backup.log 2>&1
```

Копию регулярно скачивать на другой компьютер. Ошибки смотреть в `/var/log/avar-backup.log`; автоматических уведомлений о сбоях пока нет.

На отдельной пустой установке с той же версией кода, настроенным `.env` и пустыми БД/media:

```bash
cd /opt/avar
bash deploy/restore.sh --confirm-empty-target /absolute/path/avar_TIMESTAMP.tar.gz
docker compose -f docker-compose.production.yml run --rm web python manage.py site_preflight --production
```

Первое восстановление PostgreSQL-бэкапа проверить на сервере до приглашения участников. Архивы восстановления должны происходить из доверенного источника.

## Выгрузка результатов для обучения

```bash
docker compose -f docker-compose.production.yml exec web python manage.py export_corpus /app/transfer/approved
```

CSV появятся в `transfer/approved` на сервере. `transcriptions.csv` содержит финальные правки и отдельно помеченные эталонные клипы, `recordings.csv` — только принятые записи, текст и псевдонимный speaker_id. Пути к аудио относительны media/. Паролей, логинов и отклонённых работ в CSV нет. Звуковые файлы копируются отдельно по указанным путям.

## Обновление

Сначала бэкап. Затем обновить только код, сохраняя `.env`, `media/`, `transfer/` и том PostgreSQL. Пересобрать web и повторить проверки. Не применять `down -v`: это удалит том базы. Нельзя заново импортировать старый пакет поверх новых работ участников.
