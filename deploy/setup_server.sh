#!/bin/bash
# Первичная настройка чистого Ubuntu 24.04 (запускать от root).
set -euo pipefail
apt-get update && apt-get -y upgrade
apt-get install -y ufw unattended-upgrades git ca-certificates curl
# Автообновления безопасности
dpkg-reconfigure -f noninteractive unattended-upgrades
# Файрвол: только SSH и веб
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw --force enable
# Docker
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
echo "Готово. Docker: $(docker --version)"
