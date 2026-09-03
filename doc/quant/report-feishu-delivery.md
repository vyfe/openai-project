# 策略报告 → 飞书 markdown 卡片推送（需求 1 链路）

> **状态**：已实现 / 单测 + 集成测试通过 / 等待端到端真机验收
> **最后更新**：2026-09-02
> **目标**：让用户在前端建好 IM 通道（飞书群 chat_id）后，定时调度跑策略 → 生成结构化报告 → 通过飞书 **markdown 卡片**推到群里渲染。本文档不涉及 LLM 改写（那是阶段 2）。

---

## 1. 背景

策略中心 v2 已落地（`rule_config` v1→v2 读时迁移 + 表达式沙箱 + dry-run）。报告生成链路（`run_strategy → create_report_for_run → QuantReportRecord` 含 `analysis_bundle` + `report_draft` + `final_markdown`）已通；调度器也支持 `task_type="analysis_report"` 在 `payload.channel_ids` 列里串跑多通道推送。但此前 `send_channel_content` 走的是飞书 `msg_type="text"`，**飞书 text 类型不渲染 markdown**，用户看到的是 `# 标题\n\n- 列表` 这种源码。

本次改动把推送路径从 `text` 切到 `interactive` 卡片（飞书原生 markdown 元素），并修复了 3 个前端 bug 让 IM 配置页 + 调度 IM 下拉真正可用。

---

## 2. 改动文件清单

| 文件 | 类别 | 改动要点 |
| --- | --- | --- |
| `cyf/project/server/service/quant/im_delivery_service.py` | M | 新增 `feishu_content_card()`、`send_feishu_card()`；改 `send_channel_content()` 默认走 `interactive`；`send_report_to_channel` / `send_position_summary_to_channel` / `send_test_message` 传 `title` 参数；`send_report_to_channel` 内层 try/except 已经会吞单 channel 失败 |
| `cyf/project/server/service/quant/im_service.py` | M | re-export `feishu_content_card` / `send_feishu_card` / `send_feishu_text` |
| `cyf/project/fe/src/views/quant/pages/QuantImPositionsPage.vue` | M（**bug fix**）| **bug A**：缺 `<script setup>` 块，导致 `workbench.xxx` 全 undefined → Vue 编译失败 → 整页空白。补 script setup + `refreshPositions` helper |
| `cyf/project/fe/src/views/quant/pages/QuantSchedulerPage.vue` | M（**bug fix**）| **bug B**：`schedulerMeta?.im_channel_options \|\| []` 永远空（后端 `/scheduler/meta` 从未产出此字段），导致 analysis_report 任务的"自动推送 IM 通道"下拉永远是空。改为 `workbench.imChannels`（与同文件 industry_report 分支 line 293 保持一致）|
| `cyf/project/server/tests/service/test_im_delivery_service.py` | A | 15 个单元测试（卡片构造 + 截断 + 中文 + 路径分流 + 缺 receive_id 抛错）|
| `cyf/project/server/tests/service/test_analysis_report_feishu_chain.py` | A | 3 个集成测试（调度 → 报告 → 飞书卡片 + 多通道 + 单 channel 失败鲁棒性）|

---

## 3. 端到端链路

```
[前端] /quant/im-positions
        │
        ├─ 新建 IM 通道（name + receive_id=oc_xxx + receive_id_type=chat_id）
        └─ 写库到 QuantImChannel（status=active）

[前端] /quant/strategy
        └─ 维护策略（rule_config v2 + 可选 prompt_template）

[前端] /quant/scheduler → 新建调度配置（task_type=analysis_report）
        payload = {strategy_ids: [10], channel_ids: [1], save_all_signals: true}
        cron = "20 15 * * 1-5"  (工作日 15:20)

[worker] quant_scheduler_worker (≤30s 轮询)
        ├─ enqueue_due_runs()           生成 QuantScheduleRun(status=pending, scheduled_for=匹配时间点)
        ├─ acquire_runnable_runs()      取出 pending/retry 的 run
        └─ execute_schedule_run(run_id)
                └─ task_type == "analysis_report" → execute_analysis_report(run)
                        ├─ for strategy_id in payload.strategy_ids:
                        │     strategy_run = run_strategy(...)
                        │     report = create_report_for_run(...)
                        │           └─ QuantReportRecord(analysis_bundle + report_draft + final_markdown)
                        └─ for channel_id in payload.channel_ids:
                              send_report_to_channel(report.id, channel_id=channel_id)
                                  ├─ load_channel()                取出 active IM 通道
                                  └─ send_channel_content(channel, final_markdown, title=report["title"])
                                          └─ send_feishu_card(channel, title, markdown)
                                                  ├─ feishu_content_card(title, markdown)
                                                  │     └─ JSON: {
                                                  │          config: {wide_screen_mode: true},
                                                  │          header: {title: {tag:plain_text, content}},
                                                  │          elements: [{tag:markdown, content}]
                                                  │        }
                                                  └─ lark_oapi Client.im.v1.message.create(
                                                       msg_type="interactive",
                                                       content=<上面 JSON 字符串>)
                                                  └─ 飞书渲染 markdown（标题/列表/表格/代码）
                                                  └─ 写库 QuantReportDelivery(message_type=interactive, status=success/failed)
```

---

## 4. 后端改动详解

### 4.1 飞书卡片 schema（`im_delivery_service.py:47-66`）

```python
def feishu_content_card(title: str, markdown: str) -> str:
    safe_title = (str(title or "").strip()[:80]) or "量化推送"
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": safe_title}
        },
        "elements": [
            {"tag": "markdown", "content": truncate_markdown(markdown, limit=3800)},
        ],
    }
    return json.dumps(card, ensure_ascii=False)
```

要点：
- `truncate_markdown(limit=3800)` 复用 `im_helpers.py` 既有的截断助手（飞书单 markdown 元素上限约 4000 字，留 buffer）。
- `safe_title[:80]` 防超长 title 飞书 reject。
- 中文/特殊字符靠 `ensure_ascii=False` 保留。

### 4.2 推送入口（`im_delivery_service.py:224-231`）

```python
def send_channel_content(channel, content, *, title="量化推送", message_type="interactive"):
    if message_type == "interactive":
        return send_feishu_card(channel, title=title, markdown=content)
    return send_feishu_text(channel,)
```

默认走卡片路径。reply 等场景继续走 text。

### 4.3 鲁棒性（已有，未动）

`send_report_to_channel` 内部 try/except 包住 `send_channel_content` 调用，**单 channel 失败会写到 `QuantReportDelivery.status='failed'` 但不阻塞循环**。`schedule_execution_service.execute_analysis_report` 的 for loop 因此天然容错。

---

## 5. 前端改动详解

### 5.1 `QuantImPositionsPage.vue` 补 script setup

**症状**：`/quant/im-positions` 整页空白。

**根因**：9 个 quant 页面里唯独它没有 `<script setup>` 块，template 引用 `workbench.xxx` 全 undefined → Vue 编译期就崩。

**修复**：在文件末尾补：

```vue
<script setup lang="ts">
import { RefreshRight, Setting } from '@element-plus/icons-vue'
import { useQuantWorkbench } from '@/composables/useQuantWorkbench'

const workbench = useQuantWorkbench()

const refreshPositions = () => {
  void Promise.all([
    workbench.loadPositionSummary(),
    workbench.loadPositionJournal(),
  ])
}
</script>
```

`refreshPositions` 是 template `@click="refreshPositions"`（line 168）实际需要的 helper，否则页面会报 TypeError。

### 5.2 `QuantSchedulerPage.vue` IM 下拉数据源

**症状**：`/quant/scheduler` 切到 `analysis_report` 任务，"自动推送 IM 通道" 下拉永远空，无法配多通道推送。

**根因**：`v-for="item in workbench.schedulerMeta?.im_channel_options || []"` — 后端 `/scheduler/meta` 从未产出 `im_channel_options` 字段（`schedule_query_service.py` / `scheduler_routes.py` grep 无任何 `im_channel_options`）。

**修复**：与同文件 line 293（`industry_report` 分支）一致，改用 `workbench.imChannels`：

```diff
- v-for="item in workbench.schedulerMeta?.im_channel_options || []"
+ v-for="item in workbench.imChannels"
```

---

## 6. 测试覆盖

### 6.1 单元测试 `tests/service/test_im_delivery_service.py`（15 用例）

| Test Class | 覆盖点 |
| --- | --- |
| `TestFeishuContentCard` | 7 个用例：基本 schema、空 title fallback、超长 title 截 80、超长 markdown 截 3800、未超 markdown 透传、中文 ensure_ascii=False |
| `TestSendFeishuCard` | 3 个用例：发 `interactive` msg_type、缺 receive_id 抛错、fake client 收到正确 content |
| `TestSendFeishuText` | 2 个用例：发 `text` msg_type、缺 receive_id 抛错 |
| `TestSendChannelContent` | 3 个用例：默认走 interactive、显式 `text` 走 text 路径、默认 title "量化推送" |

运行：
```bash
cd cyf/project/server && .venv/bin/python -m pytest tests/service/test_im_delivery_service.py -v
```

### 6.2 集成测试 `tests/service/test_analysis_report_feishu_chain.py`（3 用例）

| Test Case | 覆盖点 |
| --- | --- |
| `test_runs_strategy_creates_report_and_pushes_via_card` | 跑 `execute_analysis_report` happy path，spy `send_feishu_card` 验证被调用 + title 用 `report["title"]` + content 是 `report["final_markdown"]` |
| `test_pushes_to_multiple_channels_when_payload_lists_many` | payload.channel_ids=[1,2,3] 时 3 次推送，`summary.delivery_count == 3` |
| `test_failed_card_push_does_not_break_other_channels` | channel_id=1 抛 ValueError 时，其他 channel 仍能成功推送；run summary 不挂 |

Mock 策略：spy `service.quant.im_delivery_service.send_feishu_card`、`service.quant.im_channel_service.load_channel`、`run_strategy`、`create_report_for_run`、`deliver_to_bound_users`，不需要真飞书 / 真 DB。

运行：
```bash
cd cyf/project/server && .venv/bin/python -m pytest tests/service/test_analysis_report_feishu_chain.py -v
```

### 6.3 前端回归

```bash
cd cyf/project/fe && npm run test
# 89 passed (6 files)
```

`QuantImPositionsPage` 现在只剩 1 个项目共有的 `row` implicit any 警告（其他 9 个 quant 页面也有，非本次引入）。

---

## 7. 本地调试步骤

### 7.1 准备

```bash
# 后端配置（conf.ini [quant] 段）
feishu_app_id = cli_xxxxxxxxxxxx
feishu_app_secret = xxxxxxxxxxxxxxxx
```

飞书自建应用需要：
1. https://open.feishu.cn 创建应用 → 启用"机器人"能力
2. 权限：`im:message` `im:message:send_as_bot` `im:message.p2p_msg` `im:message.group_at_msg` `im:message:readonly`
3. 事件订阅 URL：`/never_guess_my_usage/quant/im/feishu/events`（如果你想机器人回复）
4. 群机器人：把应用添加为群机器人 → 拿群 `chat_id`（`oc_xxx` 开头）

### 7.2 创建 IM 通道

```bash
curl -X POST http://localhost:39997/never_guess_my_usage/quant/im/channel/create \
  -H "Authorization: Bearer <admin jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "量化日报群",
    "config": {"receive_id": "oc_真实群ID", "receive_id_type": "chat_id"},
    "description": "盘后报告推送"
  }'
```

或前端 `/quant/im-positions` → 新建通道 → 点"发送测试"，飞书群应当看到**标题为"量化 IM 测试"、内容"测试消息"渲染的卡片**。

### 7.3 创建调度配置

```bash
curl -X POST http://localhost:39997/never_guess_my_usage/quant/scheduler/config/create \
  -H "Authorization: Bearer <admin jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "盘后报告推送",
    "task_type": "analysis_report",
    "cron_expr": "*/5 * * * *",
    "payload": {"strategy_ids": [10], "channel_ids": [1], "save_all_signals": true},
    "description": "测试用每 5 分钟跑一次"
  }'
```

或前端 `/quant/scheduler` → 新建配置 → 任务类型选"测试报告" → 选策略 + 选 IM 通道 → 保存。

### 7.4 手工触发

```bash
# 立即触发
curl -X POST http://localhost:39997/never_guess_my_usage/quant/scheduler/manual_run \
  -H "Authorization: Bearer <admin jwt>" \
  -H "Content-Type: application/json" \
  -d '{"schedule_id": <id>}'

# 等几秒后查看运行结果
curl http://localhost:39997/never_guess_my_usage/quant/scheduler/run/<run_id> \
  -H "Authorization: Bearer <admin jwt>"
```

或前端 `/quant/scheduler` → 列表点"手工触发"按钮。

### 7.5 看 worker 日志

```bash
tail -f logs/quant/quant-scheduler.log
# 应看到 analysis_report_start → analysis_report_strategy → analysis_report_created → send_feishu_card
```

---

## 8. 端到端验收清单

| 步骤 | 操作 | 期望 |
| --- | --- | --- |
| 1 | 前端刷新 `/quant/im-positions` | 看到完整 IM 通道页（左栏 4 区块 + 右栏持仓）|
| 2 | 新建通道，name=测试群，receive_id=oc_真实群ID | 列表出现新行，"发送测试" 按钮可点 |
| 3 | 点"发送测试" | 飞书群收到**标题"量化 IM 测试"的 markdown 卡片**，不是源码 |
| 4 | `/quant/scheduler` → 新建配置（analysis_report + cron `*/5 * * * *`）| 选 IM 通道下拉**能列出刚才创建的通道**（不再为空）|
| 5 | 保存配置 → 列表点"手工触发" | run status 变 success；`QuantReportDelivery` 写入新记录，`message_type="interactive"`, `status="success"` |
| 6 | 飞书群 | 收到**标题为 "<策略名> · <日期> 测试报告"** 的 markdown 卡片，标题/列表/段落全部渲染 |

---

## 9. 故障排查

### 9.1 飞书群没收到消息

| 现象 | 查 | 怎么查 |
| --- | --- | --- |
| 发送测试按钮报"飞书应用 app_id/app_secret 配置缺失" | `conf.ini [quant]` 段 | 重新填 `feishu_app_id` / `feishu_app_secret` |
| 飞书回 `code != 0`（权限不足）| 应用权限 | `https://open.feishu.cn/app/<app_id>/permission` 加 `im:message` 系列 |
| 飞书回 `code=230xxx`（receive_id 无效）| 通道配置 | 检查 receive_id 是否填错；如果是群确认应用已添加为该群机器人 |
| 群收到但消息是 markdown 源码 | 走错路径 | `grep -n "msg_type" service/quant/im_delivery_service.py` 应看到 `interactive`（不是 `text`）|

### 9.2 IM 通道页空白

| 现象 | 查 | 怎么查 |
| --- | --- | --- |
| `/quant/im-positions` 完全空白 | `<script setup>` 块缺失 | `grep -n "<script" fe/src/views/quant/pages/QuantImPositionsPage.vue` 应有 `<script setup lang="ts">` |
| 控制台报 `workbench is not defined` | 同上 | 同上 |
| `refreshPositions is not defined` | helper 函数缺失 | grep `refreshPositions` 应在 script setup 内定义 |

### 9.3 调度 IM 下拉空

| 现象 | 查 | 怎么查 |
| --- | --- | --- |
| `analysis_report` 任务的"自动推送 IM 通道"下拉空 | 错用 `schedulerMeta?.im_channel_options` | `grep -n "im_channel_options" fe/src/views/quant/pages/QuantSchedulerPage.vue` 应只剩注释或为空；正确应使用 `workbench.imChannels` |
| 后端 `/scheduler/meta` 接口里没有 `im_channel_options` | 这是事实（后端没产）| 用前端 `workbench.imChannels` 即可，不需要后端新增字段 |

### 9.4 推送失败但其他正常

| 现象 | 查 |
| --- | --- |
| 单 channel 失败导致整个 run 失败 | `send_report_to_channel` 已有 try/except 包住 `send_channel_content`，单个 channel 失败只写 `QuantReportDelivery.status='failed'`，不阻塞其他 channel。检查 `execute_analysis_report` 的 for 循环有没有被外部异常打断 |
| `QuantReportDelivery.error_message` 字段含具体错误 | 该字段会写明飞书返回的错误码 + msg |

---

## 10. 已知限制 / 二阶段待办

1. **未做 LLM 改写**：`generate_report_draft` 仍是 deterministic 模板。LLM 改写按用户确认进入**阶段 2**：
   - 新建 `service/quant/report_llm_service.py`（仿 `expr_llm_service.generate_expr_from_description`）
   - `QuantPromptTemplate` 加 `model_name` 字段 + 迁移
   - `create_report_for_run` 加 `prompt_template_id` / `model_name` / `llm_enabled` 参数
   - 数值契约校验（LLM 写出的数字不在 bundle 里时 reject 重试 1 次 → 兜底模板）
   - `meta_json.model_name` + `usage` 字段写真实值
   - 前端 `QuantSchedulerPage.vue` analysis_report 分支加"AI 改写开关 + Prompt 模板下拉 + 模型下拉"

2. **消息类型选择**：当前所有推送都强制走 `interactive`。如果用户希望某些场景走 `text`（如机器人回复命令），`send_channel_content(message_type="text")` 已经支持，调用方按需传入。

3. **多频率 markdown 内容**：`final_markdown` 超 3800 字会被 `truncate_markdown` 截断。如果有用户报告内容丢失，可考虑拆成多个 markdown 元素（飞书支持 `elements: [{tag:markdown}, {tag:markdown}]`）。

4. **前端 `QuantImPositionsPage.vue:21` `row` implicit any**：项目共有的 TS 推断限制，不影响运行。

---

## 11. 引用

- 项目结构 + 量化子系统：`AGENTS.md` §1 / §3.5
- 多 LLM Provider：`AGENTS.md` §3.3（后续阶段 2 LLM 改写会用到）
- 飞书 SDK：`lark_oapi`（Python），版本见 `requirements.txt`
- 关键文件：
  - 策略执行：`service/quant/strategy_service.py`
  - 报告生成：`service/quant/report_generation_service.py` / `report_prompt_service.py` / `report_service.py`
  - 飞书推送：`service/quant/im_delivery_service.py`
  - IM 通道：`service/quant/im_channel_service.py` / `quant_entities_ops.py::QuantImChannel`
  - 调度执行：`service/quant/schedule_execution_service.py::execute_analysis_report`
  - Worker：`worker/quant_scheduler_worker.py`