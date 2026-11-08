# 慧聊登录入口与复合角色改造 · 验收报告

> 对应任务书：`doc/huiliao-login-permissions-development-plan.md`
> 基线提交：`f99f8cb`（`master`）｜执行日期：2026-11-08
> 本报告按任务书 §9.2 模板逐项填写；未实际执行的项目一律标注「未执行」，不做推断。

---

## 1. 交付范围与实现摘要

| 任务 | 状态 | 主要落点 |
| --- | --- | --- |
| D01 接口授权清单 | 完成 | `doc/huiliao-permission-route-matrix.md`（175 个端点，由 `tools/gen_permission_matrix.py` 生成） |
| D02 角色 / 归属实体与迁移 | 完成 | `model/entities.py`（`UserRole` / `VoiceAssetOwnership` / `PlatformSchemaMigration`）、`service/platform_migration.py`、`tools/platform_permissions_migrate.py`、`tools/quant_db_migrate.py` |
| D03 集中权限服务与认证 | 完成 | `service/permission_service.py`、`service/auth_service.py`、`model/repositories/user_repository.py` |
| D04 注册与用户管理契约 | 完成 | `routes/public_routes.py`（`/register`）、`routes/admin_routes.py`（`/user/*`） |
| D05 聊天与公共接口授权 | 完成 | `routes/public_routes.py` |
| D06 量化角色与资源归属 | 完成 | `routes/quant/*`、`service/quant/ownership.py`、`service/quant/{strategy,ops,position,backtest,report_generation}_service.py` |
| D07 声音角色与作品归属 | 完成 | `routes/voice_routes.py`、`routes/music_routes.py`、`routes/minimax_endpoint.py`、`service/minimax_{voice,music}_service.py` |
| D08 前端权限 / 路由 / 目的地 | 完成 | `src/auth/{permissions,apps,destination,sync}.ts`、`src/stores/auth.ts`、`src/router/index.ts`、`src/services/httpClient.ts` |
| D09 登录页与注册改造 | 完成 | `src/views/Login.vue`、`src/locales/{zh,en}/login.ts` |
| D10 顶栏与用户管理多角色 | 完成 | `src/components/layout/AppHeader.vue`、`src/components/admin/UserTable.vue` |
| D11 自动化覆盖与文档 | 完成（人工回归部分见 §4） | `cyf/project/server/tests/api/test_permission_matrix.py`、`tests/service/test_platform_migration.py`、`src/__tests__/auth/*`、`src/__tests__/stores/auth.test.ts`、`src/__tests__/views/Login.test.ts`、`src/__tests__/components/UserTable.test.ts` |
| D12 迁移演练与发布 | 部分完成（演练完成，线上发布未执行） | 见 §3、§5 |

### 1.1 授权模型要点

- 授权唯一来源是平台库 `user_role` 表；`User.role` 与 token 内嵌旧角色仅为兼容投影，不能恢复已撤销权限。
- 角色语义：`chat` / `quant` / `sound` 可自由组合，`admin` 归一为 `["admin"]` 且覆盖全部业务模块；业务角色不能推导管理员。
- 新注册账号固定授予 `["chat"]`；注册请求携带 `role` / `roles` 返回 400 且不建号。
- 权限服务集中于 `service/permission_service.py`；装饰器统一为 `require_auth`（任意已登录）、`require_module_auth(role)`、`require_admin_auth`。
- 资源归属用稳定整数 `owner_user_id`；量化 Run / Signal / Backtest / Report 继承策略归属；跨用户私有资源统一 404。
- 前端 localStorage 中的 roles 仅为恢复线索，受保护导航前必须由 `/auth/me` 完成服务端确认。

---

## 2. 执行记录

| 构建 / 提交 | 环境与数据版本 | 用例 / 命令 | 执行人 / 时间 | 结果 | 证据位置 | 缺陷 / 处理 |
| --- | --- | --- | --- | --- | --- | --- |
| 工作区（基线 `f99f8cb` + 本次改动） | 本机 macOS 15 / Python 3.9.6 / Node 20 | `.venv/bin/python -m pytest -m "not api"` | 2026-11-08 15:0x | 通过：1137 passed / 83 deselected | 本报告 §5 | 无 |
| 同上 | 同上 | `.venv/bin/python -m pytest tests/api` | 2026-11-08 15:1x | 通过：156 passed | 同上 | 无 |
| 同上 | 同上 | `npm run test`（Vitest） | 2026-11-08 15:1x | 通过：19 files / 179 tests | 同上 | 无 |
| 同上 | 同上 | `npx vue-tsc --noEmit` | 2026-11-08 15:1x | 基线 281 → 当前 257，**新增 0**（存量错误减少 24 条） | §5 | 存量错误集中在 `src/__tests__/composables/useQuantWorkbench.test.ts` 等历史用例，本次未扩大 |
| 同上 | 同上 | `npm run build`（Vite） | 2026-11-08 15:0x | 通过（19.16s，chunk 体积告警为存量现象） | §5 | 无 |
| 同上 | 本地开发库（`logs.db` / `quant.db`，存量形态） | `./start-dev.sh` | 2026-11-08 15:07 | 通过：后端 39997、前端 3000 均返回 200 | §4 | 无 |
| 同上 | 同上 | 角色矩阵端到端（4 账号 × 7 端点） | 2026-11-08 15:1x | 通过 | §3.2 | 无 |
| 同上 | 本地开发库副本 | 平台 / 量化迁移 soft 模式 + 重复执行 | 2026-11-08 15:06 | 通过（幂等） | §3.1 | 无 |

---

## 3. 迁移演练（M01–M05）

### 3.1 演练记录

对象：本地开发库 `cyf/project/server/logs.db`（8 个存量账号、52 条对话、2 条朗读）与 `quant.db`（4 条策略、2 条操作记录、9 条持仓流水），均为改造前的存量形态。

| 步骤 | 命令 | 结果 |
| --- | --- | --- |
| 平台库 dry-run | `.venv/bin/python tools/platform_permissions_migrate.py --db <logs.db> --mode dry-run --output ddl/2026-11-08_platform_permissions.sql` | 输出统计：`user=8, dialog=52, log=140, voice_reading=2, music_track=0`；角色分布 `admin=2, user=6`；未写库 |
| 平台库 soft | 同上 `--mode soft` | 自动生成 SQLite 一致性备份 `logs.db.bak.*`；建 `user_role` / `voice_asset_ownership` / `platform_schema_migration`；补 `user.deleted_at`、`voice_reading.owner_user_id`、`music_track.owner_user_id` 及索引；回填 2 个 `admin`、6 个 `chat` |
| 量化库 dry-run | `.venv/bin/python tools/quant_db_migrate.py --db <quant.db> --mode dry-run --change-name user_ownership --output ddl/2026-11-08_user_ownership.sql` | 检出缺列 `quant_strategy.owner_user_id`、`quant_operation_record.owner_user_id`、`quant_position_journal.owner_user_id` |
| 量化库 soft | 同上 `--mode soft --change-name user_ownership` | 自动生成 `quant.db.bak.*`；单事务内补列 + 重建 `quant_strategy`（解除遗留全局 `name UNIQUE`）+ 建立 `(owner_user_id, name)` 与空 owner 的 `name` 两个部分唯一索引 |
| 幂等复跑（M02） | 两个工具各再执行一次 | 角色行数不变、版本标记仍为 1 条、索引不重复、策略记录数仍为 4 |

### 3.2 演练结论

- 旧 `role=user` → `chat`、旧 `role=admin` → `admin`，回填与完成标记同事务。
- 历史业务记录 `owner_user_id` 保持为空 → 默认仅管理员可见和操作，符合任务书「不猜测归属」的保守要求。
- 未知旧角色会阻止迁移并报告，不做猜测。
- 重复执行 / 重启不会补回已撤销的权限（只处理完全没有角色行的账号）。

### 3.3 生产发布未执行项

- 线上平台库 / 量化库的一致性备份与成对恢复演练：**未执行**（需维护窗口与生产库权限）。
- R02（CDN 跨版本旧页）、R03（正式域名链路）、R04（前后端回滚演练）：**未执行**。

---

## 4. 人工回归记录

浏览器：Chromium（Playwright MCP，本机开发环境 `http://localhost:3000`）；后端 `http://127.0.0.1:39997`。

### 4.1 登录入口与视觉（V01–V03 / L01–L08）

| 用例 | 验证内容 | 结果 |
| --- | --- | --- |
| L01 默认与选择 | 默认选中「智能对话」；点击「量化研究」整卡后选中态、勾选标记与按钮文案同步为「登录并进入量化研究」 | 通过 |
| L03 未开通引导 | 仅 chat 账号选择量化登录后：保留登录态、停留当前页、展示「该功能暂未开通」、可用入口「智能对话」、联系管理员与复制按钮；点可用入口后进入 `/chat` | 通过 |
| L06 深链安全 | 未授权深链 `/quant/scheduler` → 回退到 `/login?app=quant&denied=1&required=admin` 并展示「该页面需要管理员权限」；外部 / 编码地址由 `auth/destination.ts` 拒绝（自动化覆盖） | 通过 |
| L07 已登录 / 多标签 | 已登录访问登录页展示当前账号、角色标签、切换账号与退出登录 | 通过 |
| L08 管理员入口 | 「管理员入口」复用同一登录表单，目标为 `/admin` | 通过 |
| D10 用户管理多角色 | 列表按账号显示多个角色标签；编辑弹窗正确回显「仅量化 / 仅声音 / 组合角色」；管理员开关开启时业务角色复选框禁用并提示「管理员已拥有全部业务权限」，提交 `["admin"]`；停用为独立开关 | 通过 |
| V01 尺寸 | 1440 / 1024 / 768 / 390 / 360 px 均无水平滚动（360 px 曾因顶栏按钮文案溢出，已改为窄屏仅显示图标） | 通过 |
| V02 主题 / 语言 | 亮 / 暗 × 中 / 英文切换正常，文案完整、对比度可读 | 通过 |
| V03 键盘 / 辅助 | 功能选择为原生 radio 组（`role="radiogroup"`），表单有可关联标签与可见焦点，Enter 可提交 | 通过（自动化 + 快照核对） |

证据截图：`doc/screenshots/huiliao-login-1440.png`（1440 亮色中文，含动画背景与品牌标语）、`doc/screenshots/huiliao-login-1440-dark.png`（1440 暗色）、`doc/screenshots/huiliao-login-390.png`（390 单列）、`doc/screenshots/huiliao-login-390-dark-en.png`（390 暗色英文）、`doc/screenshots/huiliao-admin-user-roles.png`（管理端多角色编辑）、`doc/screenshots/huiliao-wechat-icon.png`（微信图标）。

### 4.2 角色矩阵（A03–A05）

以 4 个演练账号对 7 个代表性端点做矩阵验证（`/split_his`、`/models/grouped`、`/quant/dashboard/overview`、`/quant/positions/summary`、`/quant/strategy/list`、`/voice/state`、`/user/list`）：

| 账号 | 角色 | 聊天 | 模型 | 量化 | 声音 | 管理 |
| --- | --- | --- | --- | --- | --- | --- |
| rehearsal_chat | `["chat"]` | 200 | 200 | 403 | 403 | 403 |
| rehearsal_quant | `["chat","quant"]` | 200 | 200 | 200 | 403 | 403 |
| rehearsal_sound | `["chat","sound"]` | 200 | 200 | 403 | 200 | 403 |
| rehearsal_admin | `["admin"]` | 200 | 200 | 200 | 200 | 200 |

- 撤权即时生效：管理员改权后，同一 access token 访问量化接口立即 403（`error_type=PERMISSION_DENIED`）；`/token/refresh` 返回的角色已是撤权后的集合，不恢复旧权限。
- 顶栏入口：仅 chat 账号只显示「智能对话」；chat+quant 账号显示「智能对话 / 量化研究」；量化导航隐藏「调度执行 / AI与记忆 / IM 通道」等管理员子页。
- 注册：携带 `role=admin` 返回 400 且不建号；正常注册返回 `roles=["chat"]`。
- 最后管理员保护、降权 / 停用 / 删除拒绝、软删除后凭据立即失效：**自动化用例覆盖**（`tests/api/test_permission_matrix.py`），线上管理员账号未被用于破坏性回归。

### 4.3 未执行项

- Safari 与真实移动设备回归：**未执行**（本机仅有 Chromium）。
- 飞书回调真实签名链路、量化 Worker / Agent 真实执行、MiniMax 付费调用：**未执行**（依赖外部凭据与付费额度，本轮以 mock 覆盖）。
- 聊天实际模型调用与 SSE 端到端录制：**未执行**（需要真实 API Key）。

---

## 5. 自动化覆盖摘要

### 5.1 新增用例

| 文件 | 覆盖用例 | 数量 |
| --- | --- | --- |
| `server/tests/api/test_permission_matrix.py` | A01–A03、A06–A07、U01–U06（8 个角色子集 × chat / quant / sound + admin + 停用 + 匿名） | 62 |
| `server/tests/service/test_platform_migration.py` | M01–M02（回填、幂等、未知旧角色阻断、版本标记） | 5 |
| `fe/src/__tests__/auth/permissions.test.ts` | 角色规范化、有效权限、兼容投影 | 11 |
| `fe/src/__tests__/auth/destination.test.ts` | 深链安全（外部 URL / 协议相对 / 编码跳转 / `..`）、目的地优先级 | 15 |
| `fe/src/__tests__/stores/auth.test.ts` | 角色快照、账号切换清理、退出清理 | 7 |
| `fe/src/__tests__/views/Login.test.ts` | L01–L05（默认选择、切换、未开通引导、注册只读权限） | 9 |
| `fe/src/__tests__/components/UserTable.test.ts` | U01–U02（多角色展示、成员筛选、roles 提交、管理员归一） | 6 |

### 5.2 命令与结果

```text
# 后端（cyf/project/server/）
.venv/bin/python -m pytest -m "not api"   → 1137 passed, 83 deselected
.venv/bin/python -m pytest tests/api      → 156 passed

# 前端（cyf/project/fe/）
npm run test        → 19 files / 179 tests passed
npx vue-tsc --noEmit → 基线 281 → 当前 257（新增 0）
npm run build       → 成功
```

---

## 6. 遗留项与风险

| 编号 | 事项 | 影响 | 建议 |
| --- | --- | --- | --- |
| R-1 | 生产库迁移与线上发布未执行 | 线上仍为旧单值 role 模型 | 按 §10.1 顺序在维护窗口执行两个迁移工具后再发布后端 |
| R-2 | 存量业务数据 `owner_user_id` 为空 | 存量策略 / 持仓 / 朗读仅管理员可见，普通用户看不到历史数据 | 需要显式认领映射；本期不默认分配 |
| R-3 | 存量自定义音色未登记归属 | 同上，仅管理员可操作 | 需要按音色清单人工认领 |
| R-4 | 飞书回调、Worker、MiniMax 付费链路未做真实回归 | 这些路径的越权防护依赖自动化 mock 结论 | 上线前在预发布用临时业务账号复测 |
| R-5 | Safari / 真实移动设备未回归 | 窄屏与键盘体验证据不完整 | 发布前在 Safari 与真机补测 |
| R-6 | `vue-tsc` 存量错误 257 条 | 不阻断构建，但会掩盖新增错误 | 本次保证新增 0；后续单独清理 |

---

## 7. 完成清单核对

- [x] D01–D12 的实现部分完成；接口清单无未分类入口（175 个端点全部标注角色）。
- [x] 新账号固定 chat；7 种普通角色组合与 admin 行为符合矩阵；改权、停用、软删除即时生效。
- [x] 登录 / 注册 / 未授权引导、深链、顶栏与管理端授权体验完成；主题、中英文、移动端、键盘回归通过。
- [x] 量化与声音的列表、详情、关联写入与文件访问按 `owner_user_id` 隔离（自动化 + 端到端矩阵覆盖）。
- [x] 迁移 dry-run、应用、幂等具备证据；启动检查会阻止缺版本的库启动。
- [x] 后端非 API 与 API 测试、前端测试、类型检查、构建与实际启动验证完成，新增失败为 0。
- [ ] CDN 跨版本旧页、API / SSE / 上传 / 音频链路验证：**未执行**（依赖线上环境）。
- [ ] 付费操作无自动重放的线上验证：**未执行**（依赖真实凭据）。
- [x] 验收报告逐项记录结果，未执行项标注「未执行」。

---

## 8. 回滚说明（摘要）

- 前端可回滚到兼容版本；新后端仍返回 `roles` 与兼容 `role`，旧前端展示有限但服务端继续执行新授权边界。
- 后端如必须回退到改造前版本，须先阻断普通用户的量化 / 声音访问并暂停相关任务，再在维护窗口恢复配套数据；不能单独回退后端而继续开放新业务角色。
- 新增的 `user_role` / `voice_asset_ownership` / `platform_schema_migration` 表与 `owner_user_id` 列在代码回退后保留，禁止直接删列清表作为常规回滚。
- 恢复后需重新验证管理员、旧 token、数据归属与启动状态。

详细发布顺序与回滚规则见 `doc/huiliao-login-permissions-development-plan.md` §10。
