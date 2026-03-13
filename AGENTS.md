# Python OpenAI 客户端-服务端项目

## 项目概述

这是一个基于 Python 的 OpenAI API 客户端-服务端项目，包含：
- Flask 后端服务（支持多 API Host、多用户/多 Key、模型过滤与缓存）
- Vue 3 + TypeScript 前端
- 旧版 CustomTkinter 桌面客户端（已基本弃用）

## 项目结构

```
cyf/
└── project/
    ├── client/              # 旧版客户端（Python/Tkinter）
    │   ├── client.py
    │   ├── client_support.py
    │   ├── client_pack.py
    │   └── conf/
    ├── fe/                  # Vue 3 前端
    │   ├── src/
    │   ├── public/
    │   ├── local-run.sh
    │   ├── server.js
    │   ├── nginx.conf.tpl
    │   ├── package.json
    │   └── vite.config.ts
    └── server/              # Flask 后端
        ├── server.py
        ├── init_model_meta.py
        ├── sqlitelog.py
        ├── local-run.sh
        ├── deploy.sh
        └── conf/
            ├── conf.ini.tpl
            └── uwsgi.ini
```

## 关键脚本

- `start-dev.sh`：本地同时启动前后端（会清理 3000/39997 端口）
- `cyf/project/server/local-run.sh`：后端本地启动，自动安装依赖并记录 `.pip_cache_timestamp`
- `cyf/project/fe/local-run.sh`：前端本地启动，自动 `npm install` 并记录 `.node_modules_timestamp`
- `start-prod.sh`：生产环境一键启动（依赖 `uwsgi` + `nginx`，解压 `server.tar.gz`/`fe.tar.gz`）
- `full-pack-prod.sh` / `pack-prod.sh`：生产打包脚本（详见根目录 README）

## 服务端 (server/)

- Flask + `openai` SDK，支持多 API Host 轮询
- `common.users` 支持多行 YAML 风格配置：`用户名:密码:可选APIKey`
- 模型列表缓存与过滤：`model_filter.include_prefixes` / `exclude_keywords` / `cache_ttl`
- Gemini 模型自动转换消息格式（文本 + `FILE_URL` 标记）
- 主要接口前缀：`/never_guess_my_usage`
  - `/login` 登录
  - `/download` 文件上传
  - `/split` / `/split_stream` 文本聊天（同步/流式）
  - `/split_pic` 图片生成
  - `/split_his` / `/split_his_content` / `/split_his_delete` 对话历史
  - `/models` / `/models/grouped` 模型列表
  - `/usage` 用量统计
  - `/test` 健康检查
- 文件上传类型：`txt`, `pdf`, `png`, `jpg`, `jpeg`, `gif`, `ppt`, `pptx`, `md`

## 前端 (fe/)

- Vue 3 + TypeScript + Vite + Element Plus
- API 地址在 `cyf/project/fe/src/services/api.ts`，开发环境默认 `http://localhost:39997`
- 支持 SSE 流式聊天（`/split_stream`）

## 配置说明 (conf/conf.ini)

- `common.upload_dir`：上传文件目录
- `common.users`：用户列表（支持多行 `user:password:optional_api_key`）
- `log.sqlite3_file`：SQLite 日志文件路径
- `api.api_key` / `api.api_host`：OpenAI Key/Host（`api_host` 支持逗号分隔）
- `api.usd_to_cny_rate`：美元到人民币转换比例
- `api.api_param_mode`：`default`（日期字符串）或 `timestamp`（毫秒时间戳）
- `model_filter.include_prefixes` / `exclude_keywords` / `cache_ttl`

## 关键运行说明

- 服务端必须在 `cyf/project/server` 目录运行（相对路径读取 `conf/conf.ini`）
- 开发默认端口：后端 `39997`，前端 `3000`
- `start-dev.sh` 默认使用根目录 `.venv/bin/python`，若不存在请先创建虚拟环境

## 前端样式注意事项

- Vue 组件内用 `:deep()` 穿透作用域样式
- `<pre>` / `<code>` 建议设置 `max-width: 100%` + `overflow-x: auto`
- 使用 `white-space: pre-wrap` 保持格式并允许换行
- 表格使用 `table-layout: fixed`
- 使用 `word-break: break-word` / `overflow-wrap: break-word` 处理长文本
- 移动端断点常用：`(max-width: 768px)`、`(max-width: 480px)`
- 处理移动端 `resize` 时避免无条件切换侧边栏状态
