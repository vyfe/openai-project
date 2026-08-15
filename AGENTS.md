# AGENTS.md — AI 编程助手指引

> 本仓库是 **Codex / Claude Code / JoyCode 等 AI 编程助手** 在此工作的首要参考资料。
> 默认中文交流；任何与本文件冲突的历史描述以本文件为准。
>
> 文档职责分工：
> - **`AGENTS.md`（本文件）**：项目知识库 + 开发约定 + 测试规范，最权威、信息最全。
> - **`README.md`**：面向用户/部署者，只讲目标、快速开始、生产部署、nginx 示例。
> - **`CLAUDE.md`**：Claude Code 的指针文件，转发到本文件，避免双份维护。
> - **`doc/` 与 `cyf/project/server/docs/`**：专题设计文档，按需引用。

---

## 0. 工作约定（最高优先级）

### 0.1 代码优化原则

在编写或修改代码后，**主动检查并消除**以下冗余：

1. **禁止重复造轮子**：优先使用项目已有依赖库中的工具方法（如 Apache Commons `StringUtils.isBlank()`、`NumberUtils.toInt()`），不要自定义功能相同的方法。
2. **消除重复 DB 查询**：同一事务内，避免先 `count()` 再 `getOne()` 查同一条数据；多个方法内部重复查询同一数据集时，查询一次后传递结果。
3. **缓存计算密集结果**：依赖图解析、JSON 遍历等耗时计算的结果应复用，不在多个方法中重复执行。
4. **简化僵尸参数**：检查方法参数是否存在值始终相同的冗余参数，直接移除。
5. **合并多次遍历**：对同一集合的多次遍历能合并就合并。

### 0.2 Zed / 工具链相关

- 若项目包含 `.zed/` 目录，且问题与 Zed 相关（tasks、debug、settings、扩展、行为差异），优先查阅 Zed 官方文档获取最新知识。
- 推荐优先查阅：<https://zed.dev/docs/tasks>

### 0.3 修改后必做

- 后端改动：在 `cyf/project/server/` 下运行 `python -m pytest -m "not api"`（最快路径）。
- 前端改动：在 `cyf/project/fe/` 下运行 `npm run test`。
- 任何触及路由/配置/启动脚本的改动，必须手动跑一次对应启动脚本验证。

---

## 1. 项目快照

**OpenAI-Project（AI 魔法棍）**：OpenAI 兼容 API 的客户端-服务端聚合代理。

| 模块 | 路径 | 技术栈 |
| --- | --- | --- |
| **后端 Web** | `cyf/project/server/` | Flask + `openai` SDK + peewee(SQLite) + JWT |
| **量化子系统** | `cyf/project/server/quant/`、`quant_client/`、`worker/`、`routes/quant/`、`service/quant/` | 自研：调度器 + 多 provider 数据采集 + 飞书 IM |
| **多 LLM Provider** | `cyf/project/server/service/{chat_service,claude_service,message_normalizer}.py` | OpenAI / Anthropic Claude / Gemini（按 `model_grp` 路由） |
| **前端 Web** | `cyf/project/fe/` | Vue 3 + TS + Vite + Pinia + Element Plus + TailwindCSS + Vue I18n + highlight.js + KaTeX + marked |
| **旧版桌面客户端** | `cyf/project/client/` | CustomTkinter，**已弃用**，仅留作参考 |

启动端口：后端 `39997`、前端 `3000`（开发），生产由 Nginx 反代。

---

## 2. 仓库结构

```
openai-project/
├── AGENTS.md                    # 本文件（AI 编程助手指引，最权威）
├── README.md                    # 面向用户/部署者
├── CLAUDE.md                    # Claude Code 指针（指向 AGENTS.md）
├── requirements.txt             # 后端 Python 依赖
│
├── start-dev.sh                 # 一键启动前后端（开发）
├── start-prod.sh                # 一键启动前后端（生产）
├── start-dev-quant              # 启动量化 Agent/Scheduler（开发）
├── start-prod-quant             # 启动量化 Agent/Scheduler（生产）
├── pack-prod.sh                 # 生产分包（生成 dist/server.tar.gz + fe.tar.gz）
├── full-pack-prod.sh            # 生产整包（生成 openai-full-prod.tar.gz）
│
├── doc/                         # 项目级专题文档
│   ├── frontend-claude-gpt-style-refactor-playbook.md
│   ├── multi-provider-refactoring-plan.md
│   └── quant/                   # 量化子系统设计/runbook
│       ├── quant-mvp-runbook.md
│       ├── a-share-data-integration-module.md
│       ├── strategy-rule-module.md
│       ├── lightweight-ai-quant-design-evaluation.md
│       ├── quant-data-collection-deploy.md
│       └── feishu-setup-guide.md
│
├── cyf/project/
│   ├── client/                  # ⚠️ 旧版 Tkinter 客户端，已弃用
│   │   ├── client.py
│   │   ├── client_support.py
│   │   └── client_pack.py
│   │
│   ├── server/                  # 后端（分层架构 + 量化子系统）
│   │   ├── server.py            # 应用入口（注册 10 个 Blueprint）
│   │   ├── server_admin.py      # 旧 admin 入口（保留兼容）
│   │   ├── server_pack.py       # 后端打包脚本
│   │   ├── sqlitelog.py         # 旧版 SQLite 日志兼容层
│   │   ├── conftest.py          # pytest 全局 fixture
│   │   ├── pytest.ini           # pytest 配置
│   │   ├── local-run.sh         # 后端本地启动
│   │   ├── deploy.sh            # 旧版部署脚本
│   │   ├── app.log              # 运行日志（轮转归档）
│   │   ├── logs.db / quant.db   # SQLite（log、quant 各自独立）
│   │   ├── backup/ dist/ logs/ run/ quant_bundles/ quant_memory/  # 运行时目录
│   │   │
│   │   ├── conf/                # 配置层
│   │   │   ├── app_factory.py   # Flask 应用工厂（含 CORS、50MB 上限）
│   │   │   ├── settings.py      # @dataclass(frozen) Settings，唯一来源
│   │   │   ├── runtime.py       # 运行时单例（含黑名单、allowed_extensions、use_db_auth）
│   │   │   ├── runtime_logging.py # 平台/量化/Ops 滚动日志分流
│   │   │   ├── logging_config.py
│   │   │   ├── uwsgi.ini
│   │   │   ├── conf.ini.tpl     # 配置模板（提交）
│   │   │   └── conf.ini         # ⚠️ 实际配置（被 .gitignore）
│   │   │
│   │   ├── routes/              # 路由层（10 个 Blueprint，全部 `/never_guess_my_usage` 前缀）
│   │   │   ├── public_routes.py        # 公共接口
│   │   │   ├── admin_routes.py         # 管理后台 CRUD
│   │   │   ├── quant_routes.py         # 量化聚合入口
│   │   │   └── quant/
│   │   │       ├── _shared.py          # 共享鉴权/装饰器
│   │   │       ├── data_routes.py      # dashboard / providers / 数据导入
│   │   │       ├── industry_routes.py  # 板块采集
│   │   │       ├── strategy_routes.py  # 策略 + Prompt 模板 + 报告
│   │   │       ├── trade_routes.py     # 持仓/运营/回测
│   │   │       ├── scheduler_routes.py # 调度器
│   │   │       ├── client_routes.py    # 数据采集 Agent 上报
│   │   │       └── im_memory_routes.py # 飞书 IM + AI 记忆
│   │   │
│   │   ├── service/             # 业务逻辑层
│   │   │   ├── chat_service.py          # OpenAI 路径主入口
│   │   │   ├── stream_service.py        # SSE 流式 + AbortController
│   │   │   ├── claude_service.py        # Claude Messages API 封装
│   │   │   ├── message_normalizer.py    # 多 provider ↔ 项目 MessagePart 协议
│   │   │   ├── model_service.py         # 模型缓存 + 过滤
│   │   │   ├── host_service.py          # API Host 轮询 + 5 分钟黑名单
│   │   │   ├── image_service.py         # 图片生成
│   │   │   ├── dialog_service.py / dialog_context_service.py
│   │   │   ├── usage_service.py / llm_usage_service.py
│   │   │   ├── auth_service.py / common_service.py / handoff_service.py
│   │   │   ├── system_prompt_service.py / notification_service.py
│   │   │   ├── bootstrap_service.py     # DB/目录/线程初始化
│   │   │   └── quant/                   # 量化业务（30+ 文件）
│   │   │       ├── strategy_service.py / binding_service.py / position_service.py
│   │   │       ├── schedule_service.py / schedule_query_service.py / schedule_execution_service.py
│   │   │       ├── schedule_log_service.py / cron_utils.py / rule_engine.py
│   │   │       ├── im_service.py / im_channel_service.py / im_delivery_service.py
│   │   │       ├── im_event_service.py / im_helpers.py / im_rules.py
│   │   │       ├── memory_service.py / report_service.py / report_generation_service.py
│   │   │       ├── report_prompt_service.py / backtest_service.py / ops_service.py
│   │   │       ├── indicator_service.py / industry_service.py
│   │   │       ├── symbol_search_service.py / task_dispatch_service.py
│   │   │       ├── query_service.py / trade_calendar_service.py / dashboard_service.py
│   │   │       ├── import_service.py / common.py
│   │   │       └── provider_{base,factory,akshare,baostock}.py
│   │   │
│   │   ├── model/               # 数据访问层
│   │   │   ├── db.py                    # 平台 SQLite（peewee）
│   │   │   ├── entities.py              # ALL_MODELS = [User, ModelMeta, ...]
│   │   │   └── repositories/
│   │   │       ├── log_repository.py    # 对话历史、上下文、日志
│   │   │       ├── model_meta_repository.py
│   │   │       └── user_repository.py
│   │   │
│   │   ├── quant/               # 量化独立数据库
│   │   │   ├── db.py                    # 独立 SQLite，避免被日志清理策略误伤
│   │   │   └── entities.py              # QUANT_MODELS
│   │   │
│   │   ├── quant_client/        # 量化 Agent 端 SDK（被 worker 复用）
│   │   │   ├── cli.py / common.py / constants.py / http_client.py
│   │   │   ├── bundle_builder.py / eastmoney_patch.py
│   │   │   └── provider_{base,factory,akshare,baostock,eastmoney,sina}.py
│   │   │
│   │   ├── worker/              # 量化独立进程（与 Web 解耦）
│   │   │   ├── quant_data_agent.py           # 数据采集 Agent（run-once 子命令）
│   │   │   ├── quant_scheduler_worker.py     # 定时调度 Worker（≤30s 轮询）
│   │   │   └── quant_feishu_ws.py            # 飞书长连接（可选）
│   │   │
│   │   ├── dto/                 # 请求/响应数据类
│   │   │   ├── auth_dto.py / chat_dto.py / dialog_dto.py / model_dto.py / common.py
│   │   │
│   │   ├── init/                # 一次性初始化脚本
│   │   │   ├── init_model_meta.py        # 从 vveai.com 拉取模型元数据
│   │   │   └── init_user_data.py         # 配置文件用户 → 数据库迁移
│   │   │
│   │   ├── tools/               # 运维脚本（check_quant_sources.py 等）
│   │   ├── test/               # 旧的调试脚本（保留兼容，非 pytest）
│   │   │
│   │   ├── tests/               # pytest 测试（unit/service/api 三层）
│   │   │   ├── unit/    test_common.py / test_claude_service.py
│   │   │   │            test_message_normalizer.py / test_cron_utils.py / test_rule_engine.py
│   │   │   ├── service/ test_binding_service.py / test_position_service.py
│   │   │   │            test_strategy_service.py / test_industry_service.py
│   │   │   │            test_schedule_log_service.py / test_schedule_query_service.py
│   │   │   └── api/     test_data_routes.py / test_trade_routes.py
│   │   │                test_strategy_routes.py / test_scheduler_routes.py
│   │   │                test_industry_routes.py / test_handoff_routes.py
│   │   │
│   │   └── docs/                # 后端专题文档
│   │       ├── notification_api_docs.md
│   │       ├── user-migration-plan.md
│   │       └── ARCHIVE_README.md
│   │
│   └── fe/                      # 前端
│       ├── package.json / vite.config.ts / vitest.config.ts / tsconfig*.json
│       ├── tailwind.config.js / index.html / test.html
│       ├── server.js            # ⚠️ 旧版 Node 模拟后端，已无用
│       ├── nginx.conf.tpl
│       ├── public/ dist/ logs/ node_modules/
│       ├── local-run.sh         # 前端本地启动（自动 npm install + 时间戳缓存）
│       └── src/
│           ├── main.ts / App.vue / i18n.ts / env.d.ts
│           ├── router/index.ts                  # /login、/chat、/admin、/quant/*
│           ├── services/                        # API 客户端
│           │   ├── httpClient.ts                # axios + JWT 自动刷新 + 401 重试
│           │   ├── api.ts / adminApi.ts / quantApi.ts
│           │   └── version.ts
│           ├── stores/auth.ts                   # 唯一 Pinia store（JWT 凭据）
│           ├── composables/
│           │   ├── useQuantWorkbench.ts         # 量化工作台（2201 行，🔴）
│           │   ├── useThemeManager.ts           # 明暗主题
│           │   ├── useNotifications.ts          # 通知轮询
│           │   └── useAdminAction.ts / useAdminCrudDialog.ts / useAdminPagedList.ts
│           ├── components/
│           │   ├── NotificationPanel.vue
│           │   ├── chat/                        # 聊天视图
│           │   │   ├── ChatContent.vue           # 2533 行，🔴
│           │   │   ├── ChatSidebar.vue           # 1288 行，🟡
│           │   │   ├── ChatToolbar.vue
│           │   │   ├── InputArea.vue
│           │   │   ├── UserSettings.vue
│           │   │   └── types.ts
│           │   └── admin/                       # Admin 后台 7 个表格
│           │       ├── ModelMetaTable.vue / SystemPromptTable.vue
│           │       ├── UserTable.vue / NotificationTable.vue
│           │       ├── TestLimitTable.vue / RuntimeOverview.vue
│           │       └── SqlExecutor.vue
│           ├── views/
│           │   ├── Login.vue / Chat.vue / Chat-New.vue / Admin.vue
│           │   └── quant/
│           │       ├── QuantLayout.vue
│           │       └── pages/
│           │           ├── QuantOverviewPage.vue / QuantDataPage.vue
│           │           ├── QuantIndustryPage.vue / QuantStrategyPage.vue
│           │           ├── QuantRunsPage.vue / QuantOperationsPage.vue
│           │           ├── QuantBacktestPage.vue / QuantSchedulerPage.vue
│           │           ├── QuantAiMemoryPage.vue / QuantImPositionsPage.vue
│           ├── plugins/element-plus.ts
│           ├── styles/                          # 16 个 CSS（含暗/亮主题、响应式）
│           ├── utils/                           # highlight.ts 及其示例/库
│           └── __tests__/                       # vitest
│               ├── setup.ts / helpers.ts
│               ├── composables/useQuantWorkbench.test.ts
│               └── services/quantApi.test.ts
│
├── .claude/                     # Claude Code 本地配置（gitignore，仅保留 settings.local.json）
│   └── settings.local.json
│
├── .codex/ environments/        # Codex 环境元数据（自动生成）
```

---

## 3. 后端详解

### 3.1 分层架构

```
HTTP ──► routes/  (Flask Blueprint)
            │   鉴权装饰器、参数解析、统一异常处理
            ▼
        service/  (业务逻辑)
            │   OpenAI / Claude / Gemini 调用、模型过滤、流式、计费
            ▼
        model/    (Peewee ORM + repositories)
            │
            ▼
        SQLite（logs.db）+ 独立 quant.db
```

- **配置唯一来源**：`conf/settings.py` 的 `Settings` dataclass（frozen）。运行时单例在 `conf/runtime.py` 的 `runtime_state`，含 `clients`、`api_host_blacklist`、`allowed_extensions`、`use_db_auth` 等可变状态。
- **应用工厂**：`conf/app_factory.py` 的 `create_app()` 启用 CORS（`*`，含凭据）、`MAX_CONTENT_LENGTH=50MB`、`@app.route("/")` 健康检查。
- **入口**：`server.py` 调用 `create_app()` 后注册 10 个 Blueprint，并执行 `bootstrap_runtime()`（DB 初始化、目录创建、黑名单清理线程、模型元数据定时刷新）。

### 3.2 接口前缀与蓝图清单

所有接口前缀为 **`/never_guess_my_usage`**。

| Blueprint | 文件 | 主要端点 |
| --- | --- | --- |
| `public_bp` | `routes/public_routes.py` | `login`、`register`、`token/refresh`、`split`、`split_stream`、`split_stream_cancel`、`split_pic`、`handoff`、`split_his{,_content,_delete}`、`update_dialog_title`、`system_prompt{,_by_group}`、`notifications`、`del_password`、`browser_conf/{get,save}`、`download`、`models`、`models/grouped`、`usage`、`test`、`set_info` |
| `admin_bp` | `routes/admin_routes.py` | `model_meta/*`、`system_prompt/*`、`test_limit/*`、`user/*`、`notification/*`、`sql_execute`（受 `enable_sql_execute` 开关保护）、`runtime/overview`、`sql/meta` |
| `quant_bp` | `routes/quant_routes.py` | 量化根级（dashboard、行情、Provider 等汇总） |
| `quant_strategy_bp` | `routes/quant/strategy_routes.py` | `strategy/*`、`symbols`、`prompt_template/*`、`reports`、`report/*` |
| `quant_trade_bp` | `routes/quant/trade_routes.py` | `positions/*`、`operations/*`、`backtest/*` |
| `quant_data_bp` | `routes/quant/data_routes.py` | `dashboard/overview`、`providers`、`data/*`、`symbols/upsert` |
| `quant_scheduler_bp` | `routes/quant/scheduler_routes.py` | `scheduler/*` |
| `quant_client_bp` | `routes/quant/client_routes.py` | `client/tasks/*`（Agent 上报） |
| `quant_industry_bp` | `routes/quant/industry_routes.py` | `industry/*` |
| `quant_im_memory_bp` | `routes/quant/im_memory_routes.py` | `im/*`、`memory/*` |

### 3.3 多 LLM Provider 路由

`model_grp` 字段（来自模型元数据或模型 id 前缀）决定路由：

| `model_grp` | 入口 | 说明 |
| --- | --- | --- |
| 默认 / `openai` 等 | `service/chat_service.py` + `openai` SDK | 多 Host 轮询，5 分钟黑名单（`host_service.random_client`） |
| `claude` | `service/claude_service.py` | Anthropic Messages API；走 `[claude]` 段独立配置（缺省回退到 `[api]`） |
| Gemini 模型 | `message_normalizer` 把 `[FILE_URL:...]` 文本标记转 `{type: "file_url"}` | 兼容 Gemini 多模态入参 |
| 多模态入参 | `message_normalizer.build_parts_from_message` + base64 内联图片 | `model_type=3` 触发 |

`service/handoff_service.py` + `/handoff` 端点用 Claude（默认模型 `claude-…-haiku`）将长会话压缩成可粘贴的交接摘要。

### 3.4 关键机制

- **Host 轮询 + 黑名单**：`host_service.random_client()` 在 `api_host_blacklist` 中选可用 host；失败后通过 `blacklist_lock` 加锁写入黑名单，`blacklist_duration = 5 * 60` 秒，后台线程到期清理。
- **模型缓存与过滤**：`model_service.get_cached_models()` 用 `runtime_state.cache_expiry_time["models"]`（默认 3600s）；`filter_models()` 只使用 `model_filter.exclude_keywords`（大小写不敏感子串匹配），按模型元数据补充 `recommend/allow_net/model_desc/model_type/model_grp` 并按 `recommend desc, meta.id desc` 排序。
- **流式 + 取消**：SSE 通过 `split_stream` 输出，`runtime_state.stream_cancel_registry` 记录可取消的会话，`split_stream_cancel` 通过 `stream_cancel_lock` 触发取消。
- **认证与权限**：默认 `use_db_auth=True`，登录走 `users` 表；JWT `access_token_ttl_seconds=1800`、`refresh_token_ttl_seconds=604800`。`/admin` 与 `/quant` 路由需要 `role=admin`（前端路由守卫 + 后端装饰器双重校验）。
- **SQL 后门**：`admin.enable_sql_execute=true` 时开启 `/sql_execute`，**生产务必保持 false**。
- **运行日志分流**：`runtime_logging.build_runtime_log_path("platform"|"quant"|"ops", ...)` 按模块分目录；普通保留 7 天，压缩保留 30 天（`runtime_log.{plain,archive}_retention_days`）。

### 3.5 量化子系统

独立于 Web 前端的子系统，含三类进程：

1. **Web 服务端**（`service/quant/` + `routes/quant/` + `quant/{db,entities}.py`）—— 提供 REST API 与独立 SQLite。
2. **数据采集 Agent**（`worker/quant_data_agent.py`）—— `run-once` 子命令向 `/client/tasks/claim` 轮询拉取任务，向 `/client/tasks/report` 上报；`start-dev-quant` / `start-prod-quant` 启动，每 15s 一次。
3. **定时调度 Worker**（`worker/quant_scheduler_worker.py`）—— 后台扫描调度表执行回测/报告生成；`≤30s` 轮询。

**Provider 多源适配**：`quant_client/provider_{akshare,baostock,eastmoney,sina}.py` 通过 `provider_factory` 选择，bash 端另有 `tools/check_quant_sources.py` 做连通性探测。

**飞书 IM**：唯一支持的 IM 通道，配置见 `[quant].feishu_*`。回调地址 `/never_guess_my_usage/quant/im/feishu/events`。

**数据流参考**：`doc/quant/quant-mvp-runbook.md`、`a-share-data-integration-module.md`、`strategy-rule-module.md`、`quant-data-collection-deploy.md`、`feishu-setup-guide.md`、`lightweight-ai-quant-design-evaluation.md`。

---


### 3.6 错误处理硬约束（项目原则）

#### 3.6.1 SSE 错误处理

> **项目原则**。一旦建立 SSE 连接，所有响应（含错误）必须遵循 SSE 格式（`data: {...}\n\n`），**不能**返回普通 JSON。已在 `stream_service.py` 与前端 SSE 解析中落地。

- `stream_service.py` 已用 `mimetype="text/event-stream"` + `Response(generator(), ...)` 包流式输出。
- 任何 SSE 端点（`/split_stream` 等）外层异常也必须 yield SSE 格式的 `error` 帧，再走 abort/关闭流程；不得用 `return jsonify({...}), 200` 中断流。
- SSE 帧格式（最小集）：
  ```python
  yield f"data: {json.dumps({'content': msg, 'done': True, 'error': error_response})}\n\n"
  ```
- 前端解析（`services/api.ts` 与 `Chat.vue`/`Chat-New.vue`）：遇到 `parsedData.error` 必须 `throw new Error(parsedData.error.msg)`，由上层统一弹错误提示，**不能**继续追加内容。

#### 3.6.2 API 异常分类

> **项目原则**。所有调用 OpenAI/Claude 路径必须走 `service/common_service.py::handle_api_exception`，禁止直接 `raise`。错误分类约定见下方返回结构。

返回结构（统一）：
```json
{
  "success": false,
  "msg": "用户友好提示",
  "error_type": "IP_RESTRICTION | AUTHENTICATION_ERROR | RATE_LIMIT_ERROR | API_ERROR | TEST_LIMIT_EXCEEDED | GENERAL_ERROR"
}
```

调用方：`chat_service.run_chat_completion`、`handoff_service.run_handoff`、`claude_service.run_claude_chat_completion` 等在捕获 `APIError/AuthenticationError/RateLimitError` 后统一转发到 `handle_api_exception`，附带 `user / model / dialog_content / url_index` 用于日志与黑名单。
## 4. 前端详解

### 4.1 路由

```
/            → /login
/login       Login.vue                  公开
/chat        Chat-New.vue               需登录
/admin       Admin.vue                  需 admin（7 个 Tab）
/quant       QuantLayout.vue + 子页面    需 admin
  ├ overview / data / industry / strategy / runs / operations
  ├ backtest / scheduler / ai-memory / im-positions
```

`Chat.vue` 是旧入口保留兼容；`Chat-New.vue` 是当前默认。

### 4.2 模块拆分

- **聊天**：`components/chat/` 下 5 个组件（`ChatContent`、`ChatSidebar`、`ChatToolbar`、`InputArea`、`UserSettings`）+ `types.ts`。
- **Admin**：`components/admin/` 下 7 个表格组件 + `views/Admin.vue` 用 Tab 切换。
- **量化**：`views/quant/pages/` 下 10 个独立页面 + `QuantLayout.vue` 公共壳。
- **状态**：仅 `stores/auth.ts`（Pinia），其余状态用 composable 内部 `ref/reactive`。
- **Composables**：`useQuantWorkbench`（2201 行 🔴 需拆分）、`useThemeManager`、`useNotifications`、`useAdminAction`、`useAdminCrudDialog`、`useAdminPagedList`。

### 4.3 API 与认证

- `services/httpClient.ts` 提供 `createApiClient({ requireAuthByDefault, publicPathPrefixes })`。
- `API_BASE_URL`：开发 `http://localhost:39997`，生产 `${protocol}//${window.location.hostname}`。
- **JWT 自动刷新**：拦截器在请求前调用 `getValidAccessToken()`，剩 30s 内提前刷新；401 后 `originalRequest._retry` 标记再重试一次。
- **公开路径白名单**：通过 `publicPathPrefixes`（如 `login`、`token/refresh`、`test`、`download`）跳过鉴权。
- **SSE 取消**：聊天页用浏览器原生 `AbortController` 调 `/split_stream_cancel`。

### 4.4 样式策略

- TailwindCSS v4 + 主题 CSS（`styles/theme-{light,dark}.css` + `tokens.css`）。
- 组件作用域样式内用 `:deep()` 穿透第三方组件库。
- 长内容容器必须设置 `max-width: 100%`、`overflow-x: auto`、`white-space: pre-wrap`。
- 表格使用 `table-layout: fixed` + `word-break: break-word`。
- 响应式断点：(max-width: 768px) / (max-width: 480px)。
- 处理移动端 `resize` 时**不要无条件切换侧边栏状态**，需对比前后状态。

### 4.5 渲染

- `marked` + `highlight.js` + KaTeX 三件套做 Markdown/代码/公式渲染。
- `html-to-image` 用于对话分享导出图片。

---

## 5. 启动脚本与运行时

### 5.1 开发环境

```bash
# 一键同时启动前后端（推荐）
./start-dev.sh
#   • 自动清理 3000 / 39997 端口
#   • 检测端口绑定权限（受限沙箱会直接报错退出）
#   • 后端日志: cyf/project/server/logs/platform/dev-backend.log
#   • 前端日志: logs/frontend/dev-frontend.log

# 分别启动
./cyf/project/server/local-run.sh     # 后端，端口 39997
./cyf/project/fe/local-run.sh         # 前端，端口 3000

# 量化子系统（独立）
./start-dev-quant                     # 默认 --all
./start-dev-quant --agent             # 仅数据采集 Agent
./start-dev-quant --scheduler         # 仅调度 Worker
```

`start-dev.sh` 使用 `.venv/bin/python`（不存在则回退 `python3`）。首次启动会自动 `pip install` / `npm install`。

### 5.2 生产环境

```bash
# 在打包机
./pack-prod.sh                        # 生成 dist/server.tar.gz + dist/fe.tar.gz
./full-pack-prod.sh                   # 生成 dist/openai-full-prod.tar.gz（一键部署包）

# 在服务器（$HOME/openai-project）
./start-prod.sh [--frontend-only | --backend-only | --all | --restart]
./start-prod-quant --all --restart    # 启动量化子系统，nohup 后台
```

`start-prod.sh` 默认运行路径是 `$HOME/openai-project`（写死在脚本顶部）。后端依赖 `uwsgi` + `nginx`；Nginx 转发示例见 `README.md` 和 `cyf/project/fe/nginx.conf.tpl`。

### 5.3 首次运行前

- `start-prod.sh` 默认无执行权限：先 `chmod +x start-prod.sh start-prod-quant`。
- `cyf/project/server/conf/conf.ini` 从 `conf.ini.tpl` 拷贝后填实际 `api_key` / `api_host` / `quant.feishu_*` 等。
- `start-prod-quant` 内置生产用户 `cyf` / `b199541d`，与生产 `conf.ini` 保持一致。

---

## 6. 配置说明（`cyf/project/server/conf/conf.ini`）

| Section | Key | 用途 |
| --- | --- | --- |
| `common` | `upload_dir` | 文件上传目录 |
| `common` | `users` | 用户列表（YAML 多行 `user:password:optional_api_key` 或逗号分隔单行） |
| `common` | `test_user` / `test_ip_default_limit` / `test_exceed_msg` | 试用账号限流 |
| `common` | `host` | HTTP Host 头（反代场景可选） |
| `log` | `sqlite3_file` | 平台 SQLite |
| `quant` | `sqlite3_file` / `bundle_dir` / `memory_dir` | 量化独立 SQLite 与目录（不要与 log 共用） |
| `quant` | `schedule_log_dir` / `schedule_log_retention_days` | 调度执行日志 |
| `quant` | `feishu_app_id` / `feishu_app_secret` / `feishu_verification_token` / `feishu_encrypt_key` / `feishu_debug_suffix` | 飞书自建应用 |
| `runtime_log` | `root_dir` / `level` / `plain_retention_days` / `archive_retention_days` / `compress_backups` | 滚动日志策略 |
| `admin` | `enable_sql_execute` | 是否开启 SQL 后门（生产务必 `false`） |
| `api` | `api_key` / `api_host` | OpenAI Key 与 Host（`api_host` 可逗号分隔多值） |
| `api` | `usd_to_cny_rate` | 美元→人民币换算 |
| `api` | `api_param_mode` | `default`（日期字符串）或 `timestamp`（毫秒） |
| `auth` | `access_token_ttl_seconds` / `refresh_token_ttl_seconds` | JWT TTL |
| `model_filter` | `cache_ttl` | 模型列表缓存秒数 |
| `model_filter` | `exclude_keywords` | **唯一生效**的过滤：子串匹配排除（大小写不敏感） |
| `model_filter` | `include_prefixes` | ⚠️ **配置项保留但代码未读取**（`settings.py` 不解析，`model_service.filter_models` 不使用）。改动它不会影响过滤行为——要改模型筛选请编辑 `exclude_keywords` 或在元数据表里维护 |
| `model_filter` | `meta_refresh_hour` / `meta_refresh_minute` / `meta_refresh_on_startup` | 模型元数据定时刷新 |
| `claude` | `api_key` / `api_host` / `api_version` | Claude SDK 独立配置，留空回退 `[api]` |

> `runtime_state.allowed_extensions = {txt,pdf,png,jpg,jpeg,gif,ppt,pptx,md}`（在 `conf/runtime.py` 硬编码，与 `[common]` 段无关）。
> `runtime_state.use_db_auth = True`（同上，硬编码）。

---

## 7. 测试规范

### 7.1 后端 pytest

```bash
cd cyf/project/server

python -m pytest                       # 全部
python -m pytest tests/unit            # 纯函数/工具类（最快）
python -m pytest tests/service         # 业务集成（需要临时 SQLite）
python -m pytest tests/api             # API 集成（需要 Flask test client）
python -m pytest -m unit               # 按标记（unit / service / api）
python -m pytest -m "not api"          # 跳过 API 测试
python -m pytest --tb=long             # 详细堆栈
python -m pytest tests/unit/test_common.py -k "test_specific"
```

- 全局 fixture 来自 `conftest.py`：session 级临时目录、`test_settings`（构造内存版 `Settings`，**不依赖 `conf.ini`**）、Flask app、临时数据库、认证客户端。
- 标记：`@pytest.mark.unit/service/api`。
- 新增 Service 函数 → `tests/service/test_*.py`；新增 API → `tests/api/test_*_routes.py`。

### 7.2 前端 Vitest

```bash
cd cyf/project/fe

npm run test                           # 一次性
npm run test:watch                     # 监听
npm run test:coverage                  # 覆盖率
```

- 配置：`vitest.config.ts`（`happy-dom`，`src/__tests__/**/*.test.ts`，覆盖率范围 `composables/` + `services/`）。
- 新增 composable → `src/__tests__/composables/*.test.ts`；新增 API 服务函数 → `src/__tests__/services/*.test.ts`。

---

## 8. 文件膨胀控制（硬性 2000 行上限）

**原则**：单一文件不得长期超过 2000 行；接近阈值即应拆分。

### 8.1 拆分策略

- **Vue 组件**：按功能区域拆子组件，单一职责。
- **Composables**：按业务领域切分为多个小 composable。
- **Python service / route**：按职责拆子模块或独立 service 文件。

### 8.2 当前需关注文件

| 文件 | 行数 | 状态 |
| --- | --- | --- |
| `fe/src/components/chat/ChatContent.vue` | 2533 | 🔴 已超标，需尽快拆分 |
| `fe/src/composables/useQuantWorkbench.ts` | 2201 | 🔴 已超标，需尽快拆分 |
| `fe/src/components/chat/ChatSidebar.vue` | 1288 | 🟡 接近阈值，需关注 |

> 行数随时间变动，以 `wc -l <file>` 为准。

---

## 9. 关键运行注意事项

- 服务端**必须在** `cyf/project/server/` 目录运行（`conf/settings.py` 用相对路径加载 `conf/conf.ini`）。
- 多进程 uWSGI 部署时，`runtime_state` 是模块级单例——黑名单、缓存、客户端列表等共享状态须注意并发安全（已用 `blacklist_lock`、`stream_cancel_lock`、`model_meta_timer_lock` 保护）。
- `start-dev.sh` 预检端口绑定权限，在受限沙箱/容器里会直接报错退出——遇到"permission:"提示说明环境不允许本地端口监听。
- 生产部署时 `admin.enable_sql_execute` 必须保持 `false`，否则暴露 SQL 后门。
- 飞书回调地址变更时同时更新 `quant.feishu_*` 与 `routes/quant/im_memory_routes.py` 中注册的路径。
- `doc/` 与 `cyf/project/server/docs/` 下的 markdown 文件**不被** `.gitignore`，是有意保留的专题文档；改动时同步更新本文件"参考文档索引"小节。`.claude/` 已被 `.gitignore` 排除，本地仅保留 `settings.local.json`。

---

## 10. 参考文档索引

### 10.1 项目级（`doc/`）

- `doc/frontend-claude-gpt-style-refactor-playbook.md` —— 前端 Claude/GPT 风格重构手册
- `doc/multi-provider-refactoring-plan.md` —— 多 LLM Provider 重构计划
- `doc/quant/quant-mvp-runbook.md` —— 量化 MVP 运行手册
- `doc/quant/a-share-data-integration-module.md` —— A 股数据集成模块
- `doc/quant/strategy-rule-module.md` —— 策略规则引擎
- `doc/quant/lightweight-ai-quant-design-evaluation.md` —— 轻量 AI 量化设计评估
- `doc/quant/quant-data-collection-deploy.md` —— 数据采集部署
- `doc/quant/feishu-setup-guide.md` —— 飞书自建应用配置

### 10.2 后端专题（`cyf/project/server/docs/`）

- `docs/notification_api_docs.md` —— 通知接口文档
- `docs/user-migration-plan.md` —— 配置文件用户迁库方案
- `docs/ARCHIVE_README.md` —— 历史归档说明

### 10.3 Claude Code 本地配置（`.claude/`，gitignore）

- `settings.local.json` —— Claude Code 权限/工具配置

> 此目录已被 `.gitignore` 排除。历史备忘（`API_EXCEPTION_HANDLING.md`、`ERROR_FEEDBACK_FIX.md`、`FRONTEND_ERROR_HANDLING_VERIFY.md`、`SSE_ERROR_HANDLING_NOTE.md`）的内容已整合到 §3.6，本地不再保留。

### 10.4 部署指引

- `README.md` —— 用户/部署者入口；包含 nginx 反代示例。
- `cyf/project/fe/nginx.conf.tpl` —— 前端 Nginx 模板。
