# 角色C开发手册：前端重构（主会话 + 子会话 + 回合栅格）

## 1. 角色目标
- 将当前单会话前端重构为“主会话容器 + 子会话列 + 回合栅格”。
- 支持动态增删模型、并行发送、单元级重试、严格对齐展示。
- 适配后端 V2 接口，同时保持旧模式可回退。

## 2. 当前问题
- `Chat-New.vue`、`ChatSidebar.vue`、`ChatContent.vue` 基于单 `messages` 数组与单模型状态。
- `selectedModel/currentDialogId/dialogTitle/isLoading` 为全局单实例，不满足并行会话。

## 3. 目标状态结构

### 3.1 store/composable 设计
- `masterSessionStore`
  - `activeMasterId`
  - `masterMeta`
  - `children[]`（列定义）
  - `rounds[]`（行定义）
  - `cellsByRoundChild`（矩阵）
- `parallelRuntimeStore`
  - `runtimeMap[roundId_childId] = { requestId, streaming, abortable, error }`

### 3.2 栅格数据视图
- 行：`rounds`（用户输入）
- 列：`children`（模型）
- 单元：`RoundCell`

## 4. 组件重构

### 4.1 `ChatSidebar`
- 展示主会话列表（只主会话）。
- 提供“添加模型/移除模型”操作。
- 不再直接控制单一 `selectedModel`。

### 4.2 `ChatContent`
- 大 Tab 对应主会话。
- 大 Tab 内渲染“回合栅格”：
  - 固定列头（模型）
  - 固定行头（回合序号/用户输入）
  - 单元内显示 streaming/success/failed/skipped。
- 单元操作：重试、停止。

### 4.3 `InputArea`
- 仅负责提交新回合输入。
- 提交后触发 `round/send`，由 store 分发更新各单元。

## 5. API 接入
- 新增 `conversationV2Api.ts`：
  - `createMaster`
  - `listMaster`
  - `getMasterDetail`
  - `addModel`
  - `removeModel`
  - `sendRound`
  - `retryCell`
- 保留 `chatAPI` 旧接口，提供 feature flag 切换。

## 6. 关键交互规则
- 动态加模型：新增列，历史行填 `skipped` 占位。
- 动态删模型：列标记 removed，可隐藏但支持恢复查看。
- 单元失败重试：仅更新该单元状态与内容。
- 历史加载：一次加载主会话全部列与行。

## 7. 严格对齐实现建议
- 使用 CSS Grid：
  - `grid-template-columns: [round] minmax(260px, 320px) repeat(n, minmax(320px, 1fr))`
- 同一行高度由内容最大单元自动撑开。
- 单元内容区域内部滚动，避免破坏行高对齐。
- 移动端降级为“行内横向滚动 + 列固定最小宽”。

## 8. 交付物
- 新 store/composable。
- 重构后的 `ChatSidebar/ChatContent/InputArea`。
- 新 API 客户端与类型定义。
- i18n 新文案（主会话、子会话、回合、单元重试、跳过占位等）。

## 9. 验收标准
- 历史列表仅展示主会话。
- 进入详情后完整恢复多模型栅格。
- 动态加模型后历史行出现 `skipped`。
- 某单元失败后重试仅影响该单元。
- 3~5模型并行时 UI/状态稳定，无串写。
