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

- 后端改动：在 `cyf/project/server/` 下运行 `python -m pytest`（全量，含 API；更快可用 `-m "not api"`）。
- 前端改动：在 `cyf/project/fe/` 下运行 `npm run test` 与 `npm run typecheck`。
- 推送前确认 `.github/workflows/ci.yml` 的三类门禁（pytest / vitest / vue-tsc + build）在本地等价通过。
- 任何触及路由/配置/启动脚本的改动，必须手动跑一次对应启动脚本验证。

---

## 1. 项目快照

**OpenAI-Project（AI 魔法棍）**：OpenAI 兼容 API 的客户端-服务端聚合代理。

| 模块 | 路径 | 技术栈 |
| --- | --- | --- |
| **后端 Web** | `cyf/project/server/` | Flask + `openai` SDK + peewee(SQLite) + 随机 Token（DB 存储） |
| **量化子系统** | `cyf/project/server/quant/`、`quant_client/`、`worker/`、`routes/quant/`、`service/quant/` | 自研：调度器 + 多 provider 数据采集 + 飞书 IM |
| **多 LLM Provider** | `cyf/project/server/service/{chat_service,claude_service,message_normalizer}.py` | OpenAI / Anthropic Claude / Gemini（按 `model_grp` 路由） |
| **前端 Web** | `cyf/project/fe/` | Vue 3 + TS + Vite + Pinia + Element Plus + TailwindCSS + Vue I18n + highlight.js + KaTeX + marked |
| **旧版桌面客户端** | `cyf/project/client/` | CustomTkinter，**已弃用**，仅留作参考 |

启动端口：后端 `39997`、前端 `3000`（开发）。生产前端由 EdgeOne Makers 托管 `chat-h.cc`；`api.chat-h.cc` 由新加坡原服务器 Nginx 反代后端。

---

## 2. 仓库结构

```
openai-project/
├── AGENTS.md                    # 本文件（AI 编程助手指引，最权威）
├── README.md                    # 面向用户/部署者
├── CLAUDE.md                    # Claude Code 指针（指向 AGENTS.md）
├── requirements.txt             # 后端 Python 依赖
├── .github/workflows/ci.yml     # GitHub Actions 门禁（pytest / vitest / vue-tsc / build）
│
├── start-dev.sh                 # 一键启动前后端（开发）
├── start-prod.sh                # 一键启动前后端（生产）
├── start-dev-quant              # 启动量化 Agent/Scheduler（开发）
├── start-prod-quant             # 启动量化 Agent/Scheduler（生产）
├── pack-prod.sh                 # 生产分包（生成 dist/server.tar.gz + fe.tar.gz）
├── full-pack-prod.sh            # 生产整包（生成 openai-full-prod.tar.gz）
│
├── doc/                         # 项目级专题文档（索引见 §10.1）
│   ├── frontend-edgeone-deployment-plan.md
│   ├── huiliao-login-permissions-development-plan.md
│   ├── huiliao-permission-route-matrix.md
│   ├── huiliao-permissions-acceptance-report.md
│   ├── minimax-voice-management.md
│   ├── minimax-music-management.md
│   ├── web-search-tool.md
│   ├── screenshots/
│   └── quant/
│       ├── data-sources-overview.md
│       ├── indicator-extension-playbook.md
│       └── report-feishu-delivery.md
│
├── cyf/project/
│   ├── client/                  # ⚠️ 旧版 Tkinter 客户端，已弃用
│   │   ├── client.py
│   │   ├── client_support.py
│   │   └── client_pack.py
│   │
│   ├── server/                  # 后端（分层架构 + 量化子系统）
│   │   ├── server.py            # 应用入口（注册 11 个 Blueprint）
│   │   ├── server_admin.py      # 旧 admin 单页入口（仅 admin_bp，端口 39998，无引用）
│   │   ├── server_pack.py       # 后端打包脚本
│   │   ├── sqlitelog.py         # 旧 SQLite 访问层（public/admin 路由仍在使用）
│   │   ├── conftest.py          # pytest 全局 fixture
│   │   ├── pytest.ini           # pytest 配置
│   │   ├── local-run.sh         # 后端本地启动
│   │   ├── deploy.sh            # 旧版部署脚本
│   │   ├── logs.db / quant.db   # SQLite（log、quant 各自独立）
│   │   ├── backup/ ddl/ dist/ docs/ logs/ quant_bundles/ quant_memory/ voice_data/  # 运行时目录
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
│   │   ├── routes/              # 路由层（11 个 Blueprint，全部 `/never_guess_my_usage` 前缀）
│   │   │   ├── public_routes.py        # 公共接口
│   │   │   ├── admin_routes.py         # 管理后台 CRUD（部分端点用 _crud_factory.py）
│   │   │   ├── _crud_factory.py       # @crud_list/@crud_get/@crud_create/@crud_update/@crud_delete 装饰器
│   │   │   └── quant/
│   │   │       ├── _shared.py          # 共享 import 聚合（当前无引用）
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
│   │   │       ├── indicator_service.py
│   │   │       ├── industry_common.py / industry_board_service.py
│   │   │       ├── industry_quote_service.py / industry_news_service.py / industry_indicator_service.py
│   │   │       ├── industry_service.py（60 行 re-export）
│   │   │       ├── symbol_search_service.py / task_dispatch_service.py
│   │   │       ├── query_service.py / trade_calendar_service.py / dashboard_service.py
│   │   │       ├── import_service.py / common.py
│   │   │       └── provider_{base,factory,akshare,baostock,tencent}.py  # 3 行 re-export → quant_client/
│   │   │
│   │   ├── model/               # 数据访问层
│   │   │   ├── db.py                    # 平台 SQLite（peewee）
│   │   │   ├── entities.py              # ALL_MODELS = [User, ModelMeta, ...]
│   │   │   └── repositories/
│   │   │       ├── log_repository.py    # 对话历史、上下文、日志
│   │   │       ├── model_meta_repository.py
│   │   │       ├── minimax_repository.py  # 音色/音乐台账
│   │   │       └── user_repository.py
│   │   │
│   │   ├── quant/               # 量化独立数据库
│   │   │   ├── db.py                    # 独立 SQLite，避免被日志清理策略误伤
│   │   │   ├── entities.py              # re-export（保留旧 import 路径）
│   │   │   ├── quant_entities_market.py    # 行情/市场数据（symbol/KLine/板块/新闻等）
│   │   │   ├── quant_entities_strategy.py  # 策略/回测/运营记录
│   │   │   └── quant_entities_ops.py        # 调度/报告/IM/记忆
│   │   │
│   │   ├── quant_client/        # 量化 Agent 端 SDK（被 worker 复用）
│   │   │   ├── cli.py / common.py / constants.py / http_client.py
│   │   │   ├── bundle_builder.py / eastmoney_patch.py
│   │   │   └── provider_{base,factory,akshare,baostock,eastmoney,sina,tencent,ths,yahoo}.py
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
│   │   ├── tools/               # check_quant_sources / gen_permission_matrix / quant_db_migrate
│   │   │                        # platform_permissions_migrate / dialog_backup 等 9 个 + ddl/
│   │   │
│   │   ├── archive_logs.py / restore_logs.py  # 对话归档/恢复 CLI（仍存在，当前无引用）
│   │   ├── tests/               # pytest：unit 27 / service 35 / api 15 个 test_*.py
│   │   │   ├── unit/            # 纯函数 / provider / 规则引擎
│   │   │   ├── service/         # 业务集成（临时 SQLite）
│   │   │   └── api/             # Flask test client
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
│           ├── locales/                       # i18n 多语言包（按域拆分）
│           │   ├── index.ts                   # 聚合 zh/en 各域
│           │   ├── zh/{chat,admin,login,validation,apps}.ts
│           │   └── en/{chat,admin,login,validation,apps}.ts
│           ├── router/index.ts                  # /login、/chat、/studio、/admin、/quant/*（meta.requiredRole）
│           ├── services/                        # API 客户端
│           │   ├── httpClient.ts                # axios + Token 自动刷新 + 401 重试
│           │   ├── api.ts / adminApi.ts / quantApi.ts
│           │   └── version.ts
│           ├── stores/auth.ts                   # 唯一 Pinia store（access/refresh token）
│           ├── composables/
│           │   ├── useQuantWorkbench.ts         # 量化工作台 facade（~2583 行，仍需拆分）
│           │   ├── quant/                       # 量化子模块
│           │   │   ├── types.ts                  # 17 个 type/interface（~225 行）
│           │   │   └── format.ts                 # 纯函数（formatRate/formatNumber/strategyStatusTag/buildSchedulePayload）
│           │   ├── chat/                        # 聊天子模块（ChatContent v2 拆分）
│           │   │   ├── chatMarkdown.ts            # Markdown/公式渲染
│           │   │   ├── messageUtils.ts            # 消息纯函数
│           │   │   ├── types.ts                   # ChatMessage / RoleSetting
│           │   │   ├── useChatExport.ts           # 截图/选中导出
│           │   │   ├── useChatMermaid.ts          # mermaid 渲染 + observer
│           │   │   ├── useChatMessageActions.ts   # 勾选/复制/删除
│           │   │   ├── useChatScroll.ts           # 滚动
│           │   │   └── useChatStream.ts           # 发送/流式/取消/重试/续写
│           │   ├── useThemeManager.ts           # 明暗主题
│           │   ├── useNotifications.ts          # 通知轮询
│           │   └── useAdminAction.ts / useAdminCrudDialog.ts / useAdminPagedList.ts
│           ├── components/
│           │   ├── NotificationPanel.vue
│           │   ├── chat/                        # 聊天视图
│           │   │   ├── ChatContent.vue           # 938 行，✅ v2 已拆分
│           │   │   ├── ChatSidebar.vue           # 1308 行，🟡
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
│           │   ├── Login.vue / Chat-New.vue / Admin.vue / Quant.vue
│           │   └── quant/
│           │       ├── QuantLayout.vue
│           │       └── pages/
│           │           ├── QuantOverviewPage.vue / QuantDataPage.vue
│           │           ├── QuantIndustryPage.vue / QuantStrategyPage.vue
│           │           ├── QuantRunsPage.vue / QuantOperationsPage.vue
│           │           ├── QuantBacktestPage.vue / QuantSchedulerPage.vue
│           │           ├── QuantAiMemoryPage.vue / QuantImPositionsPage.vue
│           ├── plugins/element-plus.ts
│           ├── styles/                          # 20 个 CSS（含暗/亮主题、响应式）
│           ├── utils/                           # highlight / mermaid / mermaidExtract / media / adminData / main
│           └── __tests__/                       # vitest
│               ├── setup.ts / helpers.ts（24 个 *.test.ts）
│               ├── auth/ 2 · components/ 7 · composables/ 5 · locales/ 1
│               └── services/ 3 · stores/ 1 · utils/ 4 · views/ 1
│
├── .claude/                     # Claude Code 本地配置（gitignore）
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
- **应用工厂**：`conf/app_factory.py` 的 `create_app()` 启用 CORS（`*`，含凭据）、`MAX_CONTENT_LENGTH=50MB`、`/` 返回 200 空体、`/health` 探针 `quant.db`（异常返回 503 `degraded`）。
- **入口**：`server.py` 调用 `create_app()` 后注册 11 个 Blueprint，并执行 `bootstrap_runtime()`（DB 初始化、目录创建、`build_clients()`、黑名单清理线程、模型元数据定时刷新、音色保活定时器、飞书 WS 线程）。

### 3.2 接口前缀与蓝图清单

所有接口前缀为 **`/never_guess_my_usage`**。

| Blueprint | 文件 | 主要端点 |
| --- | --- | --- |
| `public_bp` | `routes/public_routes.py` | `login`、`register`、`token/refresh`、`split`、`split_stream`、`split_stream_cancel`、`split_pic`、`handoff`、`split_his{,_content,_delete}`、`update_dialog_title`、`system_prompt`、`system_prompts_by_group`、`auth/me`、`notifications`、`del_password`、`browser_conf/{get,save}`、`download`、`models`、`models/grouped`、`usage`、`test`、`set_info` |
| `admin_bp` | `routes/admin_routes.py` | `model_meta/*`、`system_prompt/*`、`test_limit/*`、`user/*`、`notification/*`、`sql_execute`（受 `enable_sql_execute` 开关保护）、`runtime/overview`、`sql/meta` |
| `voice_bp` | `routes/voice_routes.py`（前缀 `/voice`） | `state`、`sync`、`clone`、`preference`、`delete`、`synthesize`、`reading/*`、`audio/*`、`profile`、`keepalive{,/run}` |
| `music_bp` | `routes/music_routes.py`（前缀 `/music`） | `state`、`generate`、`cover/preprocess`、`cover/generate`、`track/*`、`audio/*`、`delete` |
| `quant_strategy_bp` | `routes/quant/strategy_routes.py` | `strategy/*`、`symbols`、`prompt_template/*`、`reports`、`report/*` |
| `quant_trade_bp` | `routes/quant/trade_routes.py` | `positions/*`、`operations/*`、`backtest/*` |
| `quant_data_bp` | `routes/quant/data_routes.py` | `dashboard/overview`、`providers`、`data/*`、`symbols/upsert` |
| `quant_scheduler_bp` | `routes/quant/scheduler_routes.py` | `scheduler/*` |
| `quant_client_bp` | `routes/quant/client_routes.py` | `client/tasks/*`（Agent 上报） |
| `quant_industry_bp` | `routes/quant/industry_routes.py` | `industry/*` |
| `quant_im_memory_bp` | `routes/quant/im_memory_routes.py` | `im/*`、`memory/*` |

> 共 11 个 Blueprint、175 个端点（`tools/gen_permission_matrix.py` 口径）。`routes/quant_routes.py` 已删除（提交 `d3df675`），`_shared.py` 目前只是共享 import 聚合、无实际引用。

### 3.3 多 LLM Provider 路由

`model_grp` 字段（来自模型元数据或模型 id 前缀）决定路由：

| `model_grp` | 入口 | 说明 |
| --- | --- | --- |
| 默认 / `openai` 等 | `service/chat_service.py` + `openai` SDK | 多 Host 轮询，5 分钟黑名单（`host_service.random_client`） |
| `claude` | `service/claude_service.py` | Anthropic Messages API；走 `[claude]` 段独立配置（缺省回退到 `[api]`） |
| Gemini 模型 | `message_normalizer` 把 `[FILE_URL:...]` 文本标记转 `{type: "file_url"}` | 兼容 Gemini 多模态入参 |
| 多模态入参 | `message_normalizer.build_parts_from_message` + base64 内联图片 | `model_type=3` 触发 |

`service/handoff_service.py` + `/handoff` 端点把长会话压缩成可粘贴的交接摘要；模型取 `model_override` 或源对话 `modelname`（无固定默认），Claude 模型走 Claude 客户端，其余走 OpenAI 客户端。

### 3.4 关键机制

- **Host 轮询 + 黑名单**：`host_service.random_client()` 在 `api_host_blacklist` 中选可用 host；失败后通过 `blacklist_lock` 加锁写入黑名单，`blacklist_duration = 5 * 60` 秒，后台线程到期清理。
- **模型缓存与过滤**：`model_service.get_cached_models()` 用 `runtime_state.cache_expiry_time["models"]`（默认 3600s）；`filter_models()` 只使用 `model_filter.exclude_keywords`（大小写不敏感子串匹配），按模型元数据补充 `recommend/allow_net/model_desc/model_type/model_grp` 并按 `recommend desc, meta.id desc` 排序。
- **流式 + 取消**：SSE 通过 `split_stream` 输出，`runtime_state.stream_cancel_registry` 记录可取消的会话，`split_stream_cancel` 通过 `stream_cancel_lock` 触发取消。
- **认证与权限**：默认 `use_db_auth=True`，登录走 `users` 表；Token 为 **随机 opaque 串**（`secrets.token_urlsafe`，存 `users.token` JSON，不是 JWT）：`access_token_ttl_seconds=1800`、`refresh_token_ttl_seconds=604800`。模块权限由 `require_module_auth(role)` 按 `user_role` 表裁决：`/admin` 需 `admin`，`/quant` 需 `quant`，`/studio` 需 `sound`；前端路由守卫与后端装饰器双重校验。
- **SQL 后门**：`admin.enable_sql_execute=true` 时开启 `/sql_execute`，**生产务必保持 false**。
- **运行日志分流**：`runtime_logging.build_runtime_log_path("platform"|"quant"|"ops", ...)` 按模块分目录；普通保留 7 天，压缩保留 30 天（`runtime_log.{plain,archive}_retention_days`）。

### 3.5 量化子系统

独立于 Web 前端的子系统，含三类进程：

1. **Web 服务端**（`service/quant/` + `routes/quant/` + `quant/{db,entities}.py`）—— 提供 REST API 与独立 SQLite。
2. **数据采集 Agent**（`worker/quant_data_agent.py`）—— `run-once` 子命令向 `/client/tasks/claim` 轮询拉取任务，向 `/client/tasks/report` 上报；`start-dev-quant` / `start-prod-quant` 启动，每 15s 一次。
3. **定时调度 Worker**（`worker/quant_scheduler_worker.py`）—— 后台扫描调度表执行回测/报告生成；`≤30s` 轮询。

**Provider 多源适配**：`quant_client/provider_{base,factory,akshare,baostock,eastmoney,sina,tencent,ths,yahoo}.py` 通过 `provider_factory` 选择；`service/quant/provider_*.py` 只是 3 行 re-export。另有 `tools/check_quant_sources.py` 做连通性探测。

- **日线 auto 链**（2026-09-23 起）：`ths` → `baostock` → `tencent` → `sina` → `yahoo`；上游已覆盖的 symbol 不再请求下游。`ths` 需 `[quant].ths_api_key` 或 `THS_API_KEY`，缺失时跳过并降级。
- **分钟线 auto 链**：`baostock` → `eastmoney` → `sina`。
- `eastmoney` / `akshare` 已从 auto 链移除，**仅保留显式调用兼容**，会触发 `DeprecationWarning`。
- 字段完整度（13 项核心字段可填充数）：Baostock 9 > 腾讯 7 > 新浪 5；`ths` 仅日线（OHLCV + 成交额 6 项直传）。

**飞书 IM**：唯一支持的 IM 通道，配置见 `[quant].feishu_*`。回调地址 `/never_guess_my_usage/quant/im/feishu/events`。

**数据流参考**：`doc/quant/data-sources-overview.md`、`doc/quant/indicator-extension-playbook.md`、`doc/quant/report-feishu-delivery.md`。

#### 3.5.1 量化 DB schema 变更流程（必须遵守）

> **项目原则**。`quant_*` 表的列变更**禁止**靠 peewee 自动建表（仅 `safe=True` 不补列）；必须走 `tools/quant_db_migrate.py` 生成 + 落档 + 应用。

**完整流程**（新加 / 删列 / 改类型时）：

1. **改 entity**：`cyf/project/server/quant/quant_entities_*.py` 修改 `Field` 定义（`null` / `default` / 类型）。
2. **生成 ALTER SQL**：在 `cyf/project/server/` 目录跑：
   ```bash
   ../../.venv/bin/python tools/quant_db_migrate.py \
     --mode dry-run \
     --output ddl/<YYYY-MM-DD>_<change_name>.sql \
     --change-name <change_name>
   ```
   会自动扫描所有 `QUANT_MODELS`，列出缺列；落档到 `cyf/project/server/ddl/` 作为审计 / 回滚参考。
3. **应用 ALTER**（区分模式）：
   - **dev / 测试环境**：直接 `--mode hard`（无备份，假定可重置 DB）。
   - **生产环境**：必须 `--mode soft`（自动 `CREATE TABLE ... AS SELECT *` 备份 → ALTER → 提交）。
   - **线上 SQLite（生产 DB 文件）**：先 scp 备份到 `cyf/project/server/quant.db` 旁，再 `--db <线上 DB 路径> --mode soft`。
4. **跑回归**：`pytest tests/service tests/unit` 确认 entity 字段与 DB 对齐后代码能 INSERT/SELECT 成功。
5. **commit 改动**：entity 改动 + `ddl/<change_name>.sql` 一起提交；commit message 注明"需 ALTER"。

**关键约束**：

- `NOT NULL` 列必须有 `default`，否则 SQLite `ADD COLUMN` 会被拒；工具会自动检测并 fallback 为 `NULL`，并在日志里 warn。
- 备份表命名 `<原表>_backup_<YYYYMMDD_HHMMSS>_<字段名>`；运行一周无异常后手动 `DROP TABLE ...` 清理。
- `cyf/project/server/ddl/` 下的 SQL 入库作为变更证据（当前 4 份）。
- 工具支持的 entity 字段类型：`CharField / TextField / IntegerField / FloatField / BooleanField / DateTimeField / DateField / BigIntegerField`；其它类型 fallback 为 TEXT。

**工具命令总览**：

```bash
# dry-run：扫缺列并打印（默认 stdout）
../../.venv/bin/python tools/quant_db_migrate.py --mode dry-run

# dry-run + 落档
../../.venv/bin/python tools/quant_db_migrate.py \
  --mode dry-run --output ddl/2026-XX-XX_<name>.sql

# 软模式（生产）：先备份再 ALTER
../../.venv/bin/python tools/quant_db_migrate.py --mode soft

# 硬模式（dev）：直接 ALTER
../../.venv/bin/python tools/quant_db_migrate.py --mode hard

# 覆盖 DB 路径（线上 / 临时 DB）
../../.venv/bin/python tools/quant_db_migrate.py --db /path/to/quant.db --mode soft
```

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
- 前端解析（`services/api.ts` 与 `Chat-New.vue`）：遇到 `parsedData.error` 必须 `throw new Error(parsedData.error.msg)`，由上层统一弹错误提示，**不能**继续追加内容。

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
### 3.7 认证与授权（复合角色模型）

> **项目原则**。授权的唯一来源是平台库 `user_role` 表；`User.role` 与 token 内嵌的旧角色只是兼容投影，**永远不能**恢复已撤销的权限。设计依据见 `doc/huiliao-login-permissions-development-plan.md`。

#### 3.7.1 角色语义

| 存储角色 | 用户标签 | 生效范围 |
| --- | --- | --- |
| `chat` | 聊天用户 | 聊天能力及本人对话数据 |
| `quant` | 量化用户 | 量化业务能力、共享行情只读及本人研究数据 |
| `sound` | 声音用户 | 音色、语音、音乐业务及本人作品 |
| `admin` | 管理员 | 全部业务能力、全部资源及平台管理 |

- 普通账号可自由组合三种业务角色；管理员规范化为 `["admin"]`，业务角色不能推导出管理员身份。
- 新注册账号固定只授予 `["chat"]`；注册请求携带 `role` / `roles` 直接 400，不创建越权账号。
- 角色集合顺序固定为 `chat, quant, sound`（管理员单独）。

#### 3.7.2 服务端落点

| 位置 | 职责 |
| --- | --- |
| `service/permission_service.py` | 角色规范化、有效权限换算、模块/管理员检查、请求上下文（`AuthContext`） |
| `service/auth_service.py` | `require_auth` / `require_module_auth(role)` / `require_admin_auth` 装饰器、token 签发与刷新 |
| `model/repositories/user_repository.py` | `user_role` 读写、批量角色查询、原子替换角色 |
| `service/quant/ownership.py` | 量化资源归属策略（`owner_user_id`）、关联资源一致性校验 |
| `service/platform_migration.py` | 平台权限迁移版本检查与旧角色回填 |
| `tools/platform_permissions_migrate.py` | 平台库显式迁移工具（dry-run / soft / hard） |
| `tools/quant_db_migrate.py` | 量化库归属迁移（`--change-name user_ownership`） |

#### 3.7.3 错误协议

| 状态码 | 语义 | `error_type` |
| --- | --- | --- |
| 401 | 凭据缺失 / 失效 / 账号停用或软删除 | `UNAUTHENTICATED` |
| 403 | 已认证但缺少模块或操作权限（可附 `required_role`） | `PERMISSION_DENIED` |
| 404 | 资源不存在，或跨用户私有资源（统一按不存在处理） | `RESOURCE_NOT_FOUND` |
| 400 | 参数非法（含未知 / 空角色、与兼容 role 矛盾） | `VALIDATION_ERROR`（⚠️ 常量已定义但当前 400 响应未附 `error_type`） |

- 显式携带无效 bearer 时返回 401，**不**回退到请求体里的另一账号身份。
- 跨用户私有资源统一返回 404，避免暴露资源存在性。
- 撤权后旧 access 仍可认证但不再有权限；refresh 不会恢复已撤销的角色。

#### 3.7.4 资源归属

- 量化库用普通整数 `owner_user_id` 引用平台用户 `User.id`（两库之间不声明跨库外键）。
- `QuantStrategy` / `QuantOperationRecord` / `QuantPositionJournal` / `VoiceReading` / `MusicTrack` 带 `owner_user_id`；Run / Signal / Backtest / Report 继承策略归属。
- 自定义音色归属记在 `voice_asset_ownership`（唯一 `(scope, voice_id)`）；系统音色共享。
- 归属缺失的历史记录默认**仅管理员**可见和操作；普通用户不能把他人的资源链接到自己的记录。
- 策略名唯一约束为 `(owner_user_id, name)`，空 owner 另有独立 name 唯一索引。

#### 3.7.5 迁移与启动

- 存量库必须**显式**执行迁移工具后再启动；启动只校验迁移版本，缺失即阻止业务启动：

  ```bash
  # 平台库（先备份再写）
  ../../.venv/bin/python tools/platform_permissions_migrate.py --db <平台库绝对路径> --mode soft \
      --output ddl/2026-11-08_platform_permissions.sql
  # 量化库（补 owner 列 + 重建策略唯一约束）
  ../../.venv/bin/python tools/quant_db_migrate.py --db <量化库绝对路径> --mode soft \
      --change-name user_ownership --output ddl/2026-11-08_user_ownership.sql
  ```

- 回填与「完成标记」同事务；重复执行 / 重启不会补回已撤销的权限。
- 接口授权清单见 `doc/huiliao-permission-route-matrix.md`（由 `tools/gen_permission_matrix.py` 生成）；路由新增或变更必须同步更新清单与测试。

## 4. 前端详解

### 4.1 路由

```
/            → /login
/login       Login.vue                  公开
/chat        Chat-New.vue               需 chat
/admin       Admin.vue                  需 admin（7 个 Tab）
/studio      StudioLayout.vue + 子页面   需 sound
  ├ voice（音色与语音） / music（音乐创作）
/quant       QuantLayout.vue + 子页面    需 quant
  ├ overview / data / industry / strategy / runs / operations
  ├ backtest / scheduler / ai-memory / im-positions
  └ scheduler / ai-memory / im-positions 子页仍要求 admin
```

`Chat-New.vue` 是聊天页唯一入口（旧 `Chat.vue` 已移除）。

### 4.2 模块拆分

- **声音工作台**：独立功能页 `/studio`（外壳 `views/studio/StudioLayout.vue`，与量化工作台同级），左侧分区导航含“音色与语音”与“音乐创作”，入口在聊天页用户菜单。面板组件在 `components/studio/`，样式统一在 `styles/studio.css`（类名 `studio-` 前缀），两个面板的忙碌态/错误/播放器逻辑收敛到 `composables/useStudioPage.ts`，API 客户端基座在 `services/minimaxApi.ts`。
- **音色管理**：`/studio/voice`，面板 `components/studio/VoiceStudio.vue`，子组件在 `components/studio/voice/`，API 客户端为 `services/voiceApi.ts`。后端 `routes/voice_routes.py` 注册 `voice_bp`，前缀 `/never_guess_my_usage/voice`；两个蓝图共用 `routes/minimax_endpoint.py` 的鉴权与错误封装，`service/minimax_client.py` 调官方接口，`service/minimax_voice_service.py` 管理台账与音频，`service/minimax_audio.py` 落盘音频，`model/repositories/minimax_repository.py` 存台账与记录。`Settings.minimax_*` 为唯一配置来源，读取 `[minimax]`；`MINIMAX_API_KEY` 优先，不回退到聊天凭据。复用平台 SQLite 的 `voice_account_state`、`voice_reading`，保存音色台账、故事正文、生成参数及临时音频链接/24 小时过期时间；MP3 备份在被忽略的 `voice_data/`，按密钥和区域隔离。付费调用禁止自动重试，未激活音色需保留本地台账；备份失败仅重试下载，不能自动重新合成。**两套凭据**：复刻/音色查询/删除走 `[minimax_music]` 的计费密钥（Token Plan 无复刻权限），T2A 合成走 `[minimax]` 的语音密钥；`MiniMaxVoiceService` 持有 `client`（合成）与 `clone_client`（复刻）两个客户端，音色台账按复刻凭据指纹分组。**音色保活**：复刻音色 7 天未正式调用会被官方删除，`service/minimax_keepalive.py` 的每日定时器在到期前 1 天用 `clone_client` 合成一句日期播报续期（只取链接、不落本地音频、不进合成记录），保活设置存在 `voice_account_state` 台账。**音色费用**：复刻音色首次使用一次性收「音色费用」，只走账户余额、不走订阅额度（Token Plan 余额为 0 时报官方 1008）；`synthesize` 对台账中未激活的自定义音色改用 `clone_client`，遇到 1008 再换 `clone_client` 重试一次。

- **音乐创作**：`/studio/music`，面板 `components/studio/MusicStudio.vue`，子组件 `components/studio/music/MusicComposer.vue`，API 客户端为 `services/musicApi.ts`。后端 `routes/music_routes.py` 注册 `music_bp`，前缀 `/never_guess_my_usage/music`，复用管理员鉴权；`service/minimax_music_service.py` 调 `/v1/music_generation`（文本生音乐 `music-3.0`、`music-2.6`；参考音频翻唱 `music-cover` 走 `/v1/music_cover_preprocess` 两步流程），生成参数、临时音频链接/24 小时过期时间和本地 MP3 备份写入 SQLite 的 `music_track`，文件落在被忽略的 `voice_data/<凭据指纹>/music/`。风格描述必填（纯音乐时），带人声时需歌词或开启自动写词；翻唱需 6 秒–6 分钟参考音频（≤20 MB），先提取 ASR 歌词再改词生成。付费调用同样禁止自动重试，备份失败仅重试下载，不自动重新生成。共用的凭据目录与文件锁在 `service/minimax_store.py`。音乐走独立的 `[minimax_music]` 配置段（`MINIMAX_MUSIC_API_KEY` 优先），`api_key` 留空则沿用 `[minimax]` 的语音凭据；独立密钥按凭据指纹单独隔离记录与音频。新用户密钥调用音乐接口会返回官方业务码 `2153`（音乐接口不再面向新用户提供），需使用历史付费账号密钥。
- **聊天**：`components/chat/` 下 5 个组件（`ChatContent`、`ChatSidebar`、`ChatToolbar`、`InputArea`、`UserSettings`）+ `types.ts`。`ChatContent.vue` 已从 2758 行拆到 938 行：Markdown 渲染、消息纯函数、截图导出、mermaid、勾选/复制/删除、滚动、流式请求分别落在 `composables/chat/` 下 7 个模块，发送/流式/重试/续写由 `useChatStream` 统一承载。
- **Admin**：`components/admin/` 下 7 个表格组件 + `views/Admin.vue` 用 Tab 切换。
- **量化**：`views/quant/pages/` 下 10 个独立页面 + `QuantLayout.vue` 公共壳。
- **状态**：仅 `stores/auth.ts`（Pinia），其余状态用 composable 内部 `ref/reactive`。
- **Composables**：`useQuantWorkbench`（2583 行 🔴 仍超硬上限）、`composables/chat/*`（聊天链路，已拆）、`useThemeManager`、`useNotifications`、`useAdminAction`、`useAdminCrudDialog`、`useAdminPagedList`。

### 4.3 API 与认证

- `services/httpClient.ts` 提供 `createApiClient({ requireAuthByDefault, publicPathPrefixes, retryAuthOnFailure })`（`minimaxApi.ts` 显式传 `retryAuthOnFailure: false`）。
- `API_BASE_URL`：优先读取 `VITE_API_BASE_URL`；默认开发 `http://localhost:39997`、生产 `window.location.origin`。独立托管文件入口由 `VITE_FILE_BASE_URL` 指定，地址处理统一在 `services/backendUrl.ts`。
- **自动刷新**：拦截器在请求前调用 `getValidAccessToken()`，剩 30s 内提前刷新；401 后 `originalRequest._retry` 标记再重试一次。
- **公开路径白名单**：`api.ts` 只白名单 `login`、`register`；`token/refresh` 走拦截器之外的裸 `axios.post`。
- **401 / 403 分流**：401 走刷新重试（至多一次）；403 **不**刷新 token、**不**重放业务请求，只触发 `onPermissionDenied` 事件，由上层同步角色并展示权限引导。
- **会话版本**：`stores/auth.ts` 的 `sessionVersion` 在登录 / 退出 / 切换账号时自增；请求与刷新期间若版本变化，说明账号已变，直接放弃响应，避免跨账号串数据。
- **角色同步**：`auth/sync.ts::syncCurrentRoles()` 调 `/auth/me` 拉取服务端角色快照；并发调用复用同一个进行中请求。localStorage 里的 roles 只是恢复线索，受保护导航前必须完成服务端确认。
- **权限与功能入口**：`auth/permissions.ts`（角色类型与规范化）、`auth/apps.ts`（角色 → 入口 / 标签 / 图标 / 路由）、`auth/destination.ts`（目的地与深链解析）三份配置是唯一事实来源；路由用 `meta.requiredRole` 声明要求，页面与顶栏不再各自硬编码。
- **SSE 取消**：聊天页用浏览器原生 `AbortController` 调 `/split_stream_cancel`。

### 4.4 样式策略

- TailwindCSS v4 + 主题 CSS（`styles/theme-{light,dark}.css` + `tokens.css`）。
- 组件作用域样式内用 `:deep()` 穿透第三方组件库 —— **仅限 `<style scoped>` 块内**。通过非 scoped `<style>@import</style>` 引入的全局样式文件（如 `styles/admin.css`）里 `:deep()` 会失效，见 §4.7。
- 长内容容器必须设置 `max-width: 100%`、`overflow-x: auto`、`white-space: pre-wrap`。
- 表格使用 `table-layout: fixed` + `word-break: break-word`。
- 响应式断点：(max-width: 768px) / (max-width: 480px)。
- 处理移动端 `resize` 时**不要无条件切换侧边栏状态**，需对比前后状态。

### 4.5 渲染

- `marked` + `highlight.js` + KaTeX + `mermaid` 做 Markdown/代码/公式/图渲染；`DOMPurify` 负责最终 HTML 清洗。
- `html-to-image` 用于对话分享导出图片。

### 4.6 构建产物必须可复现

**硬性约束**：进入 JS chunk 的内容不得包含任何随构建变化的值（时间戳、随机数、commit hash）。

原因：前端由 EdgeOne 托管，边缘节点会缓存 `index.html`（实测 `Age` 可达 4700 秒，`Cache-Control: no-cache` 不被遵守）。若每次构建的 chunk 哈希都变，用户可能拿到旧版 HTML，而它引用的 chunk 已被新部署删除 → 资源 miss → SPA 回退返回 HTML → 浏览器按 `/assets/*` 规则缓存 → 报 `MIME type of "text/html"`，清站点缓存前无法恢复。

- 构建时间不通过 `vite define` 注入，改为由 `vite.config.ts` 的 `build-time-injector` 插件注入 `index.html` 的 `window.__BUILD_TIME__`；`src/services/version.ts` 从 `globalThis.__BUILD_TIME__` 读取。
- `__APP_VERSION__` 取 `package.json` 的 `npm_package_version`，固定值，不允许回退到时间戳。
- 改动构建配置后校验确定性：

  ```bash
  cd cyf/project/fe
  npm run build && cp -r dist /tmp/b1 && npm run build && cp -r dist /tmp/b2
  diff <(ls /tmp/b1/assets) <(ls /tmp/b2/assets)   # 应无输出
  ```

  > 两次构建必须带**相同的 `VITE_*` 环境变量**，否则 `VITE_API_BASE_URL` 一个有值一个为空，产物哈希必然不同（会误判成构建不确定）。

  详见 [`doc/frontend-edgeone-deployment-plan.md`](doc/frontend-edgeone-deployment-plan.md) §3.1。

### 4.7 主题与明暗切换

应用的明暗由 `useThemeManager` 控制（`.dark` class 挂在 `html` 与 `body`），**与操作系统配色无关**。改主题相关的样式时注意两条：

- **Tailwind v4 的 `dark:` 变体默认是 `prefers-color-scheme`**（跟随系统），`tailwind.config.js` 里的 `darkMode: 'class'` 在 v4 已失效（v4 不读该文件）。已用 `@custom-variant dark (&:where(.dark, .dark *));` 改为跟随应用主题。**项目有两份 Tailwind 入口**（`src/App.vue` 与 `src/styles/chat.css`），**两处都要声明**，否则其中一份仍是系统策略。
- **Element Plus 的暗色变量表没有引入**（未引 `element-plus/theme-chalk/dark/css-vars.css`），`--el-fill-color-*` 在暗色下会停留在冷白值，导致表格行底、斑马纹、输入框等在暗色下仍是白的。已在 `tokens.css`（亮）与 `theme-dark.css`（暗）里把 `--el-fill-color-*` 与 `--el-color-*` 映射到项目 token。
- **Element Plus 的桥接变量必须用 `:root:root`（0,2,0）压过它自己的 `:root`（0,1,0）。** 两者特异性相同时只能靠加载顺序决胜，而 Element Plus 的样式表在后 → 它赢，结果是全站 Element Plus 组件退回冷白 / EP 蓝：主按钮 `#409eff`、成功绿 `#67c23a`、边框 `#dcdfe6`、正文 `#606266`，跟项目的暖色 token 完全对不上。所以：`tokens.css` 的亮色桥接写在 `:root:root`，`theme-dark.css` 的暗色桥接写在 `:root.dark:root`（0,3,0，再高一级压过亮色块）。**新增 Element Plus 变量时按这条走，不要写进普通 `:root`。**
- 暗色下 Element Plus 的 `color-light-N` 色阶语义要反转：官方暗色表把 `light-9` 设为最深色（标签底色）、`light-3` 才最亮（hover）。沿用亮色值会让 `el-tag` 在暗色下出现亮米色底。

> ⚠ **`:deep()` 有两个坑，都表现为「规则写了但完全没效果」。**
>
> **坑一：`:deep()` 只在 `<style scoped>` 里有效。** Vue 编译器只对 scoped 样式做 `:deep()` 转换；非 scoped 样式里的 `:deep()` 会原样交给浏览器，成为**无效选择器**，整条规则被丢弃。
> - `src/styles/admin.css` 通过 Admin.vue 的**非 scoped** `<style>@import</style>` 引入。该文件曾有 124 条 `:deep()` 规则：2026-03-18（提交 `1597423`）把 Admin.vue 的 `<style scoped>` 改成 `<style>` 之前它们是生效的，之后全部失效 —— 准确表述是「**当前构建下不生效**」，不是「从未生效」。
> - `chat-responsive.css` / `chat-dark.css` 经 `chat.css` 从 Chat-New.vue 的**非 scoped** 块引入，其中 45 条 `:deep()` 同样失效（暗色代码块底色、引用块橙边、移动端代码块/表格尺寸等全都没生效）。
> - Chat-New.vue 自己的 `.chat-tabs-wrap` 规则也在提交 `04e3ad3` 去掉 `<style scoped>` 后失效（工作台 tab 固定宽度那组）。
>
> **坑二：同一个选择器里不能出现两个 `:deep()`。** Vue 的 scoped 插件遇到**第一个** `:deep()` 就会 `return false` 停止处理该选择器，第二个 `:deep()` 原样留在产物里 → 死规则。`global-font-sizes.css` 里的 `.messages-container :deep(.message-text) :deep(code)` 就踩了这个坑（52 处），导致消息里代码块/表格/标题的字号没跟着字号设置走。正确写法：同组件内的元素直接写普通类名，只对 v-html 渲染出来的节点保留最后一个 `:deep()`。
>
> **改法约定**：
> - 目标是 v-html 渲染的节点（`pre` / `code` / `table` / `th`…）→ 规则必须放进**某个组件的 `<style scoped>` 块**，靠 `:deep()` 穿透。聊天页的消息区覆盖统一放在 `src/styles/chat-message-content.css`，由 `ChatContent.vue` 的 scoped 块**最后**引入（保证与基础样式特异性相同时由它胜出）。
> - 目标是页面自身的元素（`.admin-page` / `.chat-tabs-wrap` 等）→ 用普通后代选择器 + 宿主类名前缀限定范围，不要用 `:deep()`。
> - `el-select` / `el-dropdown` / `el-message-box` 会 teleport 到 body，页面作用域命不中，它们的暗色样式由 `App.vue` 的 `body.dark-theme` 规则统一处理；`el-dialog` 默认 `appendToBody=false`，渲染在组件原位，`.admin-page .el-dialog` 可以命中。
>
> **自查**：`npm run build` 后 `grep -o ':deep(' dist/assets/*.css | wc -l` 必须是 0 —— 产物里还有字面 `:deep(` 就说明又写出了死规则。

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

`start-dev.sh` 直接使用 `.venv/bin/python`（不存在则回退 `python3`）运行 `server.py` 与 `npm run dev`，**不会安装依赖**；首次准备请先跑 `local-run.sh`。开发默认使用 `conf/conf.dev.ini`（由 `QUANT_CONF_PATH` 指定，已被 gitignore）。

### 5.2 生产环境

当前生产分离部署：前端 `chat-h.cc` 由 EdgeOne Makers 项目 `makers-ewkduzmpajma` 发布，生产分支 `codex/edgeone-frontend-deploy`、构建根目录 `cyf/project/fe`；两个 `VITE_*_BASE_URL` 均为 `https://api.chat-h.cc`。push 到该分支自动触发构建流水线，在 EdgeOne 控制台点击发布后生效。Spaceship 根域 CNAME 已指向 EdgeOne，免费证书已部署并启用 HTTP 到 HTTPS 的 301 跳转。`preview.chat-h.cc` 关联同一生产环境。API、数据库、附件、量化与音频继续由新加坡原服务器运行。

前端改动经测试后集成到生产分支并 push，在 EdgeOne 检查对应 commit 的流水线构建成功并点击发布；后端使用下方 `--backend-only --restart`。完整 DNS、证书、宝塔任务、前后端发布和回滚步骤见 [`doc/frontend-edgeone-deployment-plan.md`](doc/frontend-edgeone-deployment-plan.md)。

```bash
# 在打包机
./pack-prod.sh                        # 生成 dist/server.tar.gz + dist/fe.tar.gz（fe.tar.gz 已弃用，前端改由 EdgeOne 构建）
./full-pack-prod.sh                   # 生成 dist/openai-full-prod.tar.gz（一键部署包）

# 在服务器（$HOME/openai-project）
./start-prod.sh [--frontend-only | --backend-only | --all | --restart]
./start-prod-quant --all --restart    # 启动量化子系统，nohup 后台
```

> 前端已由 EdgeOne 从 Git 分支自动构建，`pack-prod.sh` 产出的 `fe.tar.gz` 与 `start-prod.sh --frontend-only` 仅保留给原服务器静态站回滚，日常发布不用。

`start-prod.sh` 默认运行路径是 `$HOME/openai-project`（写死在脚本顶部）。后端依赖 `uwsgi` + `nginx`；Nginx 转发示例见 `README.md` 和 `cyf/project/fe/nginx.conf.tpl`。

### 5.3 首次运行前

- `start-prod.sh` 默认无执行权限：先 `chmod +x start-prod.sh`（`start-prod-quant` 已带可执行位）。
- `cyf/project/server/conf/conf.ini` 从 `conf.ini.tpl` 拷贝后填实际 `api_key` / `api_host` / `quant.ths_api_key` / `quant.feishu_*` 等。
- `start-prod-quant` 的 Agent 登录凭据不再内置于脚本：优先读环境变量 `QUANT_LOGIN_USER` / `QUANT_LOGIN_PASSWORD`，其次读服务器受控文件 `$HOME/openai-project/.quant-credentials`（每行 `KEY=VALUE`，权限 600）；两者都缺失时脚本明确报错退出。首次切换需在服务器创建该文件，调度 Worker 不需要凭据。
- 该文件同样走「模板 → 复制 → 填值」模式：仓库根目录 [`.quant-credentials.tpl`](.quant-credentials.tpl) 是只有占位符的模板，部署时 `cp .quant-credentials.tpl .quant-credentials` 后填入实际账号并 `chmod 600`。与 `conf.ini.tpl` 一样，模板入库、实际文件由 `.gitignore` 拦截。

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
| `quant` | `ths_api_key` | 同花顺数据 API Key（留空用 `THS_API_KEY`；auto 链首选） |
| `quant` | `feishu_app_id` / `feishu_app_secret` / `feishu_verification_token` / `feishu_encrypt_key` / `feishu_debug_suffix` | 飞书自建应用 |
| `runtime_log` | `root_dir` / `level` / `plain_retention_days` / `archive_retention_days` / `compress_backups` | 滚动日志策略 |
| `admin` | `enable_sql_execute` | 是否开启 SQL 后门（生产务必 `false`） |
| `api` | `api_key` / `api_host` | OpenAI Key 与 Host（`api_host` 可逗号分隔多值） |
| `api` | `usd_to_cny_rate` | 美元→人民币换算 |
| `api` | `api_param_mode` | `default`（日期字符串）或 `timestamp`（毫秒） |
| `auth` | `access_token_ttl_seconds` / `refresh_token_ttl_seconds` | 访问 / 刷新 Token TTL（opaque token，非 JWT；`conf.ini.tpl` 未提供该段，默认 1800 / 604800） |
| `model_filter` | `cache_ttl` | 模型列表缓存秒数 |
| `model_filter` | `exclude_keywords` | **唯一生效**的过滤：子串匹配排除（大小写不敏感） |
| `model_filter` | `include_prefixes` | ⚠️ **配置项保留但代码未读取**（`settings.py` 不解析，`model_service.filter_models` 不使用）。改动它不会影响过滤行为——要改模型筛选请编辑 `exclude_keywords` 或在元数据表里维护 |
| `model_filter` | `meta_refresh_hour` / `meta_refresh_minute` / `meta_refresh_on_startup` | 模型元数据定时刷新 |
| `claude` | `api_key` / `api_host` / `api_version` | Claude SDK 独立配置，留空回退 `[api]`；`conf.ini.tpl` 未提供该段，需自加 |
| `tools` | `web_search_*`（8 键） | 服务端本地网络搜索 |
| `minimax` | `api_key` / `region` / `key_kind` / `model` / `timeout_seconds` / `storage_dir` | 语音凭据（`MINIMAX_API_KEY` 优先，不回退聊天凭据） |
| `minimax_music` | `api_key` / `region` / `key_kind` / `model` / `timeout_seconds` | 音乐/复刻凭据（留空回退 `[minimax]`） |

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
- 当前 24 个测试文件 / 210 个用例（含 `components/ChatContent.test.ts` 与 `composables/chat*` / `useChat*` 单测）。
- 新增 composable → `src/__tests__/composables/*.test.ts`；新增 API 服务函数 → `src/__tests__/services/*.test.ts`。

### 7.3 CI 门禁（GitHub Actions）

`.github/workflows/ci.yml` 在每次 push / pull_request 触发，两个 job：

| Job | 内容 |
| --- | --- |
| `backend` | Python 3.9 + `requirements.txt`，`python -m pytest -q`（全量，含 API） |
| `frontend` | Node 20 + `npm ci`，依次跑 `npm run typecheck`（`vue-tsc --noEmit`）、`npm run test`（vitest）、`npm run build` |

- `npm run build` 本身**不做类型检查**，类型门禁只有 `typecheck`；本地改完前端必须自己先跑一遍。
- CI 与生产部署解耦：EdgeOne 仍从生产分支构建前端，CI 只负责拦截回归。

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
| `fe/src/components/chat/ChatContent.vue` | 938 | ✅ v2 已拆为 `composables/chat/*`（原 2758 行） |
| `fe/src/composables/useQuantWorkbench.ts` | 2583 | 🔴 仍超硬上限，v2 候选 |
| `fe/src/components/chat/ChatSidebar.vue` | 1308 | 🟡 接近阈值，v2 候选 |
| `fe/src/views/Login.vue` | 1227 | 🟡 接近阈值 |
| `fe/src/styles/chat-sidebar.css` | 1224 | 🟡 纯样式，可按域拆分 |
| `fe/src/i18n.ts` | 18 | ✅ v1 已拆为 locales/{zh,en}/{chat,admin,login,validation,apps}.ts |
| `cyf/project/server/service/quant/industry_service.py` | 60 | ✅ v1 已拆为 5 个子 service（re-export 兼容） |
| `cyf/project/server/quant/entities.py` | 74 | ✅ v1 已拆为 3 个 quant_entities_*.py（re-export 兼容） |
| `cyf/project/server/routes/admin_routes.py` | 747 | ✅ v1 用 _crud_factory.py 统一部分端点 |

> 行数随时间变动，以 `wc -l <file>` 为准。

---

## 9. 关键运行注意事项

- 服务端**建议**在 `cyf/project/server/` 目录运行（uWSGI 与相对 DB 路径按此约定）；`conf/settings.py` 实际用 `BASE_DIR=__file__` 定位配置，cwd 不影响读取，可用 `QUANT_CONF_PATH` 覆盖（`start-dev.sh` 指向 `conf/conf.dev.ini`）。
- 多进程 uWSGI 部署时，`runtime_state` 是模块级单例——黑名单、缓存、客户端列表等共享状态须注意并发安全（已用 `blacklist_lock`、`stream_cancel_lock`、`model_meta_timer_lock` 保护）。
- `start-dev.sh` 预检端口绑定权限，在受限沙箱/容器里会直接报错退出——遇到"permission:"提示说明环境不允许本地端口监听。
- 生产部署时 `admin.enable_sql_execute` 必须保持 `false`，否则暴露 SQL 后门。
- 飞书回调地址变更时同时更新 `quant.feishu_*` 与 `routes/quant/im_memory_routes.py` 中注册的路径。
- 量化子系统 DB schema 变更必须走 `tools/quant_db_migrate.py`（见 §3.5.1）；禁止靠 peewee 自动建表补缺列。
- **禁止把生产密钥写进仓库**：`conf/conf.ini.tpl` 只放占位符，同花顺 / MiniMax / 飞书 / OpenAI 等 Key 一律留在服务器 `conf/conf.ini` 或环境变量；量化数据库备份（`*.db.bak*`）、`.priv` 私钥文件不得提交（已在 `.gitignore` 中拦截）。历史提交里出现过的明文密码，**必须轮换密码**，仅删除文件无效。
- `doc/` 与 `cyf/project/server/docs/` 下的 markdown 文件**不被** `.gitignore`，是有意保留的专题文档；改动时同步更新本文件"参考文档索引"小节。`.claude/` 已被 `.gitignore` 排除，本地含 `settings.local.json`、`launch.json`、`plans/`。

---

## 10. 参考文档索引

### 10.1 项目级（`doc/`）

- `doc/huiliao-login-permissions-development-plan.md` —— 慧聊登录入口、复合角色与资源隔离的开发任务、测试回归及发布验收。
- `doc/huiliao-permission-route-matrix.md` —— 全量接口授权清单（方法、路径、角色、读写范围、关联资源、旧认证兼容、对应测试）。
- `doc/huiliao-permissions-acceptance-report.md` —— 本期改造的验收报告（执行记录、证据、遗留项与回滚说明）。
- `doc/minimax-voice-management.md` —— MiniMax 音色配置、复刻/激活、后台操作与 API。
- `doc/minimax-music-management.md` —— MiniMax 音乐创作配置、生成流程、记录保存与 API。
- `doc/web-search-tool.md` —— 服务端本地网络搜索工具的工作方式与配置。
- `doc/quant/data-sources-overview.md` —— 行情数据源总览（provider 能力对比与选型）。
- `doc/quant/indicator-extension-playbook.md` —— 量化指标横向扩展开发指南（registry → compute → IDE/回测/测试 五步）
- `doc/quant/report-feishu-delivery.md` —— 报告 → 飞书投递链路

> 索引只列仓库内实际存在的文档；新增或删除 `doc/` 下文件时同步维护本节，避免死链。

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
- `doc/frontend-edgeone-deployment-plan.md` —— 当前 EdgeOne/API 架构、各平台配置、宝塔续签、前后端发布及回滚手册。
- `cyf/project/fe/nginx-api.conf.tpl` —— 独立 HTTPS API 与文件入口模板。
- `cyf/project/fe/verify-deploy.sh` —— 线上前端部署自检：静态资源 MIME 类型与缓存策略。
