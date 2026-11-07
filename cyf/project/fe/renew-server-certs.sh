#!/usr/bin/env bash
set -euo pipefail
umask 077

# 由宝塔原有“续签Let's Encrypt证书”计划任务以 root 每日执行。
exec 9>/run/openai-server-cert-renew.lock
flock -n 9 || exit 0

cd /www/server/panel
renew_status=0
./pyenv/bin/python3 -u class/acme_v2.py --renew=1 || renew_status=$?

# API 手工配置的 vhost 可能不在宝塔站点列表内，单独检查以确保覆盖。
cert_dir=/www/server/panel/vhost/letsencrypt/api.chat-h.cc
if openssl x509 -checkend 2592000 -noout -in "$cert_dir/fullchain.pem"; then
  printf '%s\n' 'api.chat-h.cc: 证书剩余有效期超过 30 天，无需续签。'
else
  ./pyenv/bin/python3 -u class/acme_v2.py \
    --domain api.chat-h.cc --type http --path /www/wwwroot/api.chat-h.cc
  openssl x509 -checkend 2592000 -noout -in "$cert_dir/fullchain.pem"
  chmod 600 "$cert_dir/privkey.pem"
  /www/server/nginx/sbin/nginx -t
  /www/server/nginx/sbin/nginx -s reload
fi

exit "$renew_status"
