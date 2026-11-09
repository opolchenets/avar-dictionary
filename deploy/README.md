# Развёртывание на сервере (Ubuntu 24.04, Docker, Caddy)

1. **Ключ SSH** создаётся на своём ПК (`ssh-keygen -t ed25519`), публичный ключ кладётся
   на сервер (`~/.ssh/authorized_keys`). После проверки входа по ключу в
   `/etc/ssh/sshd_config.d/00-keys-only.conf` пишется `PasswordAuthentication no`,
   затем `systemctl restart ssh`.
2. **Настройка сервера:** `bash deploy/setup_server.sh` (обновления, файрвол 22/80/443, Docker).
3. **Код:** `git clone https://github.com/opolchenets/avar-dictionary.git /opt/avar`.
4. **Секреты:** `cp .env.example .env`, заполнить: `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`
   (длинные случайные строки, `openssl rand -base64 48`), `DJANGO_DEBUG=False`,
   `SITE_DOMAIN`, `DJANGO_ALLOWED_HOSTS=<домен>`,
   `DJANGO_CSRF_TRUSTED_ORIGINS=https://<домен>`. Файл `.env` в git не попадает.
5. **DNS:** A-запись домена → IP сервера.
6. **Запуск:**
   `docker compose -f docker-compose.yml -f docker-compose.caddy.yml up -d --build`
   Caddy сам получит HTTPS-сертификат.
7. **Админ и данные:**
   `docker compose exec web python manage.py createsuperuser`,
   затем `import_clips` / `import_prompts` (папки с фрагментами копируются на сервер через `scp`).
8. **Бэкап:** в `crontab -e` добавить
   `30 3 * * * /opt/avar/deploy/backup.sh >> /var/log/avar-backup.log 2>&1`.
   Скачать к себе: `scp -r root@<IP>:/root/backups .`
