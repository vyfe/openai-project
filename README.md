# OpenAI-Project · AI 魔法棍

> OpenAI 兼容 API 的客户端-服务端聚合代理。
> 内置 **聊天（多 LLM Provider）** 与 **A 股量化子系统** 两大模块。

- 详细的项目结构、API 端点、Provider 路由、测试规范等 → [`AGENTS.md`](./AGENTS.md)
- 多 Provider 重构、量化设计等专题文档 → [`doc/`](./doc/)
- Claude Code 工作指引 → [`CLAUDE.md`](./CLAUDE.md)

---

## 1. 功能特性

### 1.1 聊天 / 多 LLM 对话
- **OpenAI / Anthropic Claude / Gemini** 多 Provider 自动路由（`model_grp` 决定）
- 多 API Host 轮询 + 失败自动拉黑 5 分钟
- 多用户、多 Key、模型过滤与缓存
- SSE 流式输出 + 浏览器 AbortController 取消
- 文件上传（`txt/pdf/png/jpg/jpeg/gif/ppt/pptx/md`，单文件最大 50MB）
- JWT 双 Token 鉴权 + 401 自动刷新
- Gemini `[FILE_URL:...]` 文本标记自动转多模态入参
- 长会话 `/handoff` 上下文压缩（Claude 驱动）

### 1.2 管理后台（`/admin`）
- 模型元数据 / 系统提示词 / 用户 / 通知 / 试用限流 的 CRUD
- 运行时总览（黑名单、缓存、token 统计）
- 受开关保护的 SQL 后门（**生产务必关闭**）

### 1.3 量化子系统（`/quant`）
- A 股行情采集（akshare / baostock / eastmoney / sina 多 provider）
- 板块采集、策略规则引擎、报告生成
- 独立 SQLite（与日志库隔离）、调度器、回测
- 飞书自建应用 IM 通道：双向对话、报告推送、持仓录入
- 数据采集 Agent + 定时调度 Worker 独立进程

---

## 2. 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 Web | Python 3 · Flask · `openai` SDK · peewee (SQLite) · JWT |
| 量化 | 自研多 provider · APScheduler 风格调度 · 飞书 SDK |
| 前端 | Vue 3 · TypeScript · Vite · Pinia · Element Plus · TailwindCSS v4 · Vue I18n · highlight.js · KaTeX · marked |

---

## 3. 快速开始（开发模式）

```bash
# 1. 准备虚拟环境（如已有 .venv 可跳过）
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. 复制后端配置并填入 Key
cp cyf/project/server/conf/conf.ini.tpl cyf/project/server/conf/conf.ini
$EDITOR cyf/project/server/conf/conf.ini

# 3. 一键启动前后端
./start-dev.sh
#   前端 http://localhost:3000
#   后端 http://localhost:39997
```

`start-dev.sh` 会自动清理 3000 / 39997 端口、检测绑定权限、启动后端（后台） + 前端（前台）。
按 Ctrl+C 同时停止两个服务。

也可单独启动：

```bash
./cyf/project/server/local-run.sh     # 仅后端
./cyf/project/fe/local-run.sh         # 仅前端
```

启动量化子系统（独立进程）：

```bash
./start-dev-quant                     # 数据采集 Agent + 调度 Worker
./start-dev-quant --agent             # 仅数据采集 Agent（15s 轮询）
./start-dev-quant --scheduler         # 仅调度 Worker（≤30s 轮询）
```

---

## 4. 部署

### 4.1 打包（在开发机）

```bash
./pack-prod.sh        # → dist/server.tar.gz + dist/fe.tar.gz
./full-pack-prod.sh   # → dist/openai-full-prod.tar.gz（一键部署包，含 start-prod.sh / start-prod-quant / requirements.txt）
```

### 4.2 部署（在生产服务器）

```bash
# 解压
tar -xzf openai-full-prod.tar.gz
cd dist

# 写好配置
cp cyf/project/server/conf/conf.ini.tpl cyf/project/server/conf/conf.ini
$EDITOR cyf/project/server/conf/conf.ini    # api_key / api_host / quant.feishu_*

# 启动（首次运行需 chmod）
chmod +x start-prod.sh start-prod-quant
./start-prod.sh --all                        # 前后端
nohup ./start-prod-quant --all --restart > start-prod-quant.out 2>&1 &   # 量化子系统
```

生产依赖：`python3` + `uwsgi` + `nginx`。

### 4.3 Nginx 反代示例

```nginx
server {
    listen ${backend_port};
    server_name localhost;

    # 把 `/never_guess_my_usage/*` 反代到 uWSGI（端口见 start-prod.sh）
    location ~* /never_guess_my_usage {
        proxy_pass http://127.0.0.1:${backend_real_port};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        return 403;
    }
}

server {
    listen 80;
    server_name openai-chat;

    # 前端静态文件（SPA 路由）
    location / {
        root ${PROJECT_ROOT}/cyf/project/fe;
        index index.html;
        try_files $uri $uri/ /index.html;
    }
}
```

模板见 [`cyf/project/fe/nginx.conf.tpl`](./cyf/project/fe/nginx.conf.tpl)。

---

## 5. 配置说明

后端配置入口：`cyf/project/server/conf/conf.ini`（从 `conf.ini.tpl` 复制）。

| Section | 关键 Key | 说明 |
| --- | --- | --- |
| `common` | `upload_dir` / `users` / `host` | 上传目录 / 用户列表（`user:password:optional_api_key` 多行 YAML）/ 反代 Host 头 |
| `log` | `sqlite3_file` | 平台 SQLite |
| `quant` | `sqlite3_file` / `feishu_*` | 量化独立 SQLite / 飞书自建应用 |
| `runtime_log` | `root_dir` / `level` / `*_retention_days` / `compress_backups` | 滚动日志策略 |
| `admin` | `enable_sql_execute` | SQL 后门开关（**生产务必 `false`**） |
| `api` | `api_key` / `api_host` / `usd_to_cny_rate` / `api_param_mode` | OpenAI Key / Host（多值逗号分隔）/ 汇率 / 时间格式 |
| `auth` | `access_token_ttl_seconds` / `refresh_token_ttl_seconds` | JWT TTL |
| `model_filter` | `cache_ttl` / `exclude_keywords` / `meta_refresh_*` | 实际生效的过滤仅 `exclude_keywords`（`include_prefixes` 已废弃，未被代码读取） |
| `claude` | `api_key` / `api_host` / `api_version` | Claude 独立配置；留空回退 `[api]` |

完整 Key 清单与默认值见 [`AGENTS.md` 第 6 节](./AGENTS.md#6-配置说明cyfprojectserverconfconfini)。

---

## 6. 关键运行注意

- **后端必须**在 `cyf/project/server/` 目录运行（用相对路径读 `conf/conf.ini`）。
- 生产 `admin.enable_sql_execute` 必须为 `false`。
- 多进程 uWSGI 部署时注意 `runtime_state` 是模块级单例，共享状态已有锁保护（黑名单、流取消、模型元数据定时器）。
- `start-prod.sh` 默认运行路径 `$HOME/openai-project`，需根据实际调整脚本顶部 `PROJECT_ROOT`。
- `start-prod-quant` 内置生产账号 `cyf` / `b199541d`，与生产 `conf.ini` 的 `users` 保持一致。
- 旧版 Tkinter 客户端（`cyf/project/client/`）与 `cyf/project/fe/server.js`（旧 Node 模拟后端）已弃用，仅作历史参考。
- 详细测试规范、文件膨胀控制、AI 编程助手约定见 [`AGENTS.md`](./AGENTS.md)。

---

## 7. 安全

- 用户认证默认走数据库（`use_db_auth=True`），`users` 段是单一来源。
- JWT 双 Token：`Authorization: Bearer <access_token>`，刷新走 `POST /never_guess_my_usage/token/refresh`。
- 文件上传白名单硬编码在 `conf/runtime.py::RuntimeState.allowed_extensions`。
- SQL 后门必须保持关闭（生产由运维侧审计 `enable_sql_execute` 配置）。
- `cyf/project/*/conf/conf.ini` 与 `cyf/project/*/conf/key.*` 已在 `.gitignore` 内，禁止提交。
- 飞书回调需校验 `feishu_verification_token` 与 `feishu_encrypt_key`。

---

## 8. 许可证

仅作个人/团队内部使用，未声明开源许可。
