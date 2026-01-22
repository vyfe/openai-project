server {
    listen 80;
    server_name _;

    # 前端静态文件 (修改为实际路径)
    location / {
        root /home/{{username}}/openai-project/cyf/project/fe/dist;
        index index.html;
        try_files $uri $uri/ /index.html;  # SPA 路由支持
    }

    # API 代理到后端
    location /api {
        proxy_pass http://127.0.0.1:39997;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 其他API路由代理到后端
    location /health {
        proxy_pass http://127.0.0.1:39997;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /upload {
        proxy_pass http://127.0.0.1:39997;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /models {
        proxy_pass http://127.0.0.1:39997;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}