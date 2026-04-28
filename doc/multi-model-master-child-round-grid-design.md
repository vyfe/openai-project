# 多模型并行会话产品模型重设计（主会话 + 子会话 + 回合栅格）

## 1. 背景与目标

### 1.1 核心目标
- `Tab` 拆分的第一目标是支持独立并行会话，而不是单纯做多模型展示。
- 多模型对比是建立在并行会话能力之上的产品形态。
- 采用统一模型：一个“大 Tab（主会话）”管理多个“并行子会话（模型执行流）”。
- 展示层采用“回合栅格（行=回合，列=模型）”并保持严格对齐，方便横向比较。

### 1.2 已确认策略
- 子会话集合允许动态增删，并保留历史。
- 主界面采用回合栅格视图。
- 历史会话列表只展示主会话，不展示子会话。
- 子会话失败支持单元级重试（仅重试当前轮当前模型单元格）。

## 2. 产品模型（定稿）

### 2.1 实体分层

#### 主会话（MasterConversation）
- 字段：
  - `master_id`
  - `title`
  - `session_type`（`single` | `multi_compare`）
  - `active_models[]`
  - `owner`
  - `created_at`
  - `updated_at`
- 职责：
  - 编排一次多模型并行实验。
  - 作为历史会话列表的唯一展示入口。

#### 子会话（ChildConversation）
- 字段：
  - `child_id`
  - `master_id`
  - `model_id`
  - `status`（`active` | `removed` | `failed`）
  - `backend_dialog_id`（可空）
  - `created_round_index`
- 职责：
  - 承载某模型在主会话中的独立执行链路与上下文。

#### 回合（Round）
- 字段：
  - `round_id`
  - `master_id`
  - `round_index`
  - `user_prompt`
  - `attachments`
  - `created_at`
- 职责：
  - 作为多模型结果的对齐锚点（每行一个用户输入回合）。

#### 回合单元（RoundCell）
- 字段：
  - `round_id`
  - `child_id`
  - `assistant_output`
  - `cell_status`（`success` | `streaming` | `failed` | `skipped`）
  - `error`
  - `latency`
- 职责：
  - 表示“某模型在某回合”的独立结果。
  - 支持单元级重试。

## 3. 交互与展示语义

### 3.1 大 Tab / 子会话关系
- 大 Tab 对应主会话。
- 大 Tab 内部展示回合栅格。
- 列为子会话（模型），行为回合。

### 3.2 历史加载
- 历史列表只展示主会话摘要。
- 点击主会话后，自动加载该主会话下全部子会话与回合单元，并在同一大 Tab 内渲染。

### 3.3 动态增删模型
- 增加模型：新增一列子会话，从当前回合开始参与，历史回合填 `skipped` 占位。
- 删除模型：默认软删除（`removed`），不硬删历史数据，保障可追溯。

### 3.4 失败与重试
- 单元失败后，允许点击该单元独立重试。
- 重试范围仅限该 `RoundCell`，不影响其他模型/回合。

## 4. 前后端演进与接口设计

### 4.1 当前现状
- 现有后端 `Dialog` 为单表单模型单会话结构（`modelname/dialog_name/context`）。
- 现有 `split_his` 返回单会话列表，无法表达主子会话与回合矩阵。

### 4.2 演进建议
- 新增会话结构（推荐）：
  - `master_conversation`
  - `child_conversation`
  - `round_cell`（`round` 可单表或嵌入）
- 保留旧接口兼容，新增 V2 接口：
  - `POST /conversation/master/create`
  - `POST /conversation/master/list`（仅主会话）
  - `POST /conversation/master/detail`（主会话 + 子会话 + 回合栅格）
  - `POST /conversation/master/add_model`
  - `POST /conversation/master/remove_model`
  - `POST /conversation/round/send`（一次输入 fan-out 到多个子会话）
  - `POST /conversation/cell/retry`（单元级重试）

### 4.3 迁移策略
- 旧 `Dialog` 继续可读。
- 用户首次进入新模式时，按需迁移为 `single` 主会话（1 主 1 子）。
- 新旧模式可并行运行，逐步切流。

## 5. 前端重构落地方案

### 5.1 状态层
- 新增 `masterSessionStore`：
  - 当前主会话元信息
  - 子会话列定义
  - 回合列表
  - 栅格矩阵（`rounds + cellsByChild`）
- 新增 `parallelRuntimeStore`：
  - 子会话运行时状态（`requestId`、`abortController`、`streaming`、失败态）

### 5.2 组件职责
- `ChatSidebar`：
  - 主会话列表
  - 模型集合管理（增删模型）
- `ChatContent`：
  - 大 Tab 容器
  - 回合栅格渲染
  - 单元操作（重试、停止）
- `InputArea`：
  - 只负责创建回合输入
  - 不再直接绑定单一模型会话

### 5.3 并行执行策略
- 每次发送产生一个新回合。
- 对当前 `active_models` 并发请求，分别写入对应 `RoundCell`。
- 每个单元独立状态机：`idle -> streaming -> success|failed`。
- 单元重试只重入本单元状态机。

## 6. 验收标准

### 6.1 产品验收
- 多模型主会话中，列宽固定，行高按行内最大内容统一，视觉严格对齐。
- 动态加模型后，历史轮有 `skipped` 占位；当前及后续轮正常并发输出。
- 某模型某轮失败仅影响该单元；单元重试仅更新该单元。
- 历史列表只出现主会话；进入详情后一次恢复全部子会话列。

### 6.2 技术验收
- 并发 3~5 模型时，停止/重试操作互不干扰。
- 单元级错误与流式中断不会污染其它单元状态。
- 旧单会话数据仍可读；迁移后可在新模型下浏览。

## 7. 假设与默认
- 多模型对比仅在 `session_type=multi_compare` 启用；`single` 维持轻量。
- 子会话删除默认软删除（可恢复）。
- 对齐可比性优先于单条消息流式体验，但保留流式能力。

## 8. 里程碑建议
- M1：前端纯内存模型（无后端改造）验证回合栅格与单元重试交互。
- M2：后端落地主子会话数据结构与 V2 接口。
- M3：新旧数据兼容迁移与灰度发布。
- M4：性能优化（并发控制、虚拟滚动、长会话渲染优化）。
