# 安装到宝塔 vhost/nginx；先准备 api.chat-h.cc 的 DNS A 记录与证书。
# map 位于 http 上下文；仅固定前端域名可跨域调用 API。
map $http_origin $openai_frontend_origin {
    default "";
    "https://chat-h.cc" $http_origin;
    "https://preview.chat-h.cc" $http_origin;
    "http://localhost:3000" $http_origin;
}

server {
    listen 80;
    server_name api.chat-h.cc;
    location ^~ /.well-known/acme-challenge/ {
        root /www/wwwroot/api.chat-h.cc;
    }
    location / { return 301 https://api.chat-h.cc$request_uri; }
}

server {
    listen 443 ssl http2;
    server_name api.chat-h.cc;
    ssl_certificate /www/server/panel/vhost/cert/api.chat-h.cc/fullchain.pem;
    ssl_certificate_key /www/server/panel/vhost/cert/api.chat-h.cc/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    client_max_body_size 50m;

    # 上游旧 CORS 头在此统一替换，避免重复头和 wildcard + credentials。
    proxy_hide_header Access-Control-Allow-Origin;
    proxy_hide_header Access-Control-Allow-Credentials;
    proxy_hide_header Access-Control-Allow-Headers;
    proxy_hide_header Access-Control-Allow-Methods;
    add_header Access-Control-Allow-Origin $openai_frontend_origin always;
    add_header Access-Control-Allow-Headers "Content-Type,Authorization,X-Requested-With,Cache-Control" always;
    add_header Access-Control-Allow-Methods "GET,POST,PUT,DELETE,OPTIONS" always;
    add_header Vary Origin always;
    add_header Cache-Control "private, no-store" always;

    location /never_guess_my_usage/ {
        if ($request_method = OPTIONS) { return 204; }
        proxy_pass http://127.0.0.1:39997;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 900s;
        proxy_send_timeout 900s;
    }
    location = /health { proxy_pass http://127.0.0.1:39997; }
    location /download/ {
        alias /home/www/downloads/;
        autoindex off;
    }
    location / { return 404; }
}
