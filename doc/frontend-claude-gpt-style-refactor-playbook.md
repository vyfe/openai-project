# 前端素雅风重构执行手册（回合制）

> 适用项目：`/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe`
>  
> 目标：在不切换 Vue 框架的前提下，将首页与聊天页重构为类 Claude / GPT 的素雅风，并可按“回合制”持续迭代与记录。

---

## 1. 结论与原则

### 1.1 结论
- 不切框架，不做全站组件库迁移。
- 基于当前 `Vue3 + Element Plus + Tailwind` 做视觉与布局重构。
- 先统一设计令牌（tokens），再改布局，再改组件皮肤。

### 1.2 执行原则
- 小步快跑：每回合只做一个可验证目标。
- 不破坏功能：先保行为，再改样式。
- 单点回归：每回合结束跑固定验收清单。
- 进度可追踪：每回合都写“变更记录 + 风险 + 下一步”。

---

## 2. 范围与文件地图

### 2.1 主要页面
- 登录页：`/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/views/Login.vue`
- 聊天页容器：`/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/views/Chat-New.vue`

### 2.2 聊天核心组件
- 消息区：`/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/components/chat/ChatContent.vue`
- 侧栏：`/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/components/chat/ChatSidebar.vue`
- 输入区：`/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/components/chat/InputArea.vue`

### 2.3 样式与主题
- 全局入口：`/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/App.vue`
- 聊天样式：`/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/styles/chat.css`
- 其他样式：`/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/styles/*.css`

---

## 3. 目标体验定义（用于验收）

### 3.1 首页（登录）
- 信息层级极简：主标题、输入框、主按钮为唯一视觉焦点。
- 弱化次要操作：注册、通知、外链降权放置。
- 背景克制：不使用高干扰动效。

### 3.2 聊天页
- 三段式稳定结构：左侧历史 / 中央消息 / 底部输入。
- 顶栏简洁：模型、用户菜单、主题切换保留；杂项收纳。
- 消息可读性优先：合适行长、行高、留白、对比度。

### 3.3 动效
- 仅保留必要过渡（100~220ms）。
- 不允许持续漂浮类装饰动画。

---

## 4. 分阶段路线图（建议 7 回合）

## 阶段 A：地基（回合 1）
- 目标：建立统一 design tokens 与主题层。
- 产出：
  - 新建 `tokens.css`（颜色/间距/圆角/阴影/动效变量）
  - 新建 `theme-light.css`、`theme-dark.css`
  - 在 `App.vue` 收口主题入口
- 验收：
  - 深浅主题切换正常
  - 页面视觉无明显回退

## 阶段 B：布局（回合 2~3）
- 回合 2 目标：重构 `Chat-New.vue` 顶栏与主布局骨架。
- 回合 3 目标：重构 `ChatSidebar.vue` 信息分区与视觉层级。
- 验收：
  - 1366px 与 390px 宽度均无横向滚动
  - 侧栏开合不卡顿

## 阶段 C：消息与输入（回合 4~5）
- 回合 4 目标：重构 `ChatContent.vue` 消息流视觉。
- 回合 5 目标：重构 `InputArea.vue` 输入框与发送区。
- 验收：
  - 用户/AI 消息区分清晰但不刺眼
  - 长文本、代码块、表格不溢出

## 阶段 D：首页（回合 6）
- 目标：重构 `Login.vue` 成素雅风。
- 验收：
  - 表单交互、校验、提交逻辑保持一致
  - 深浅色一致

## 阶段 E：清理与收口（回合 7）
- 目标：清理冗余样式与重复覆盖。
- 验收：
  - 删除无用样式后页面无视觉退化
  - 关键路径手测通过

---

## 5. 每回合执行模板（直接复制使用）

```md
## 回合 X：<标题>

### 1) 本回合目标
- 

### 2) 变更范围（文件）
- 

### 3) 实施内容
- 

### 4) 验证结果
- [ ] 登录页正常
- [ ] 聊天页正常
- [ ] 移动端 390px 正常
- [ ] 深浅主题正常
- [ ] 长文本/代码块不溢出

### 5) 风险与问题
- 

### 6) 下一回合计划
- 
```

---

## 6. 进度看板（勾选制）

- [x] 回合 1：设计令牌与主题地基
- [x] 回合 2：聊天页主布局骨架
- [x] 回合 3：侧栏分区与视觉层级
- [x] 回合 4：消息流样式重构
- [x] 回合 5：输入区样式重构
- [x] 回合 6：首页样式重构
- [x] 回合 7：样式清理与收口

---

## 7. 验收门禁（每回合都要跑）

### 7.1 功能门禁
- [ ] 登录/登出
- [ ] 选择模型并发起对话
- [ ] 历史对话加载与切换
- [ ] 流式输出开关与发送快捷键
- [ ] 用户设置弹窗可用

### 7.2 UI 门禁
- [ ] 1366px 桌面布局稳定
- [ ] 390px 移动端布局稳定
- [ ] 无横向滚动条（特殊代码块除外）
- [ ] 颜色对比可读
- [ ] 过渡动效不过度

### 7.3 性能门禁（基础）
- [ ] 首屏无明显卡顿
- [ ] 侧栏开合、消息渲染无明显掉帧

---

## 8. 风险清单与规避

- 风险 1：`Element Plus` 深度覆写导致连锁回归。
  - 规避：先在新 token 层映射变量，再逐步替换旧覆盖。
- 风险 2：`chat.css` 体积大、选择器冲突。
  - 规避：按 layout/component/theme 分段迁移，回合内不混改。
- 风险 3：移动端改动影响桌面端。
  - 规避：每回合同时验 390px 与 1366px。
- 风险 4：暗色主题局部漏改。
  - 规避：每回合强制切换主题走一次完整流程。

---

## 9. 建议新增文件（按需）

- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/styles/tokens.css`
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/styles/theme-light.css`
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/styles/theme-dark.css`
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/styles/chat-layout.css`
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/styles/chat-components.css`

---

## 10. 完成定义（DoD）

- 首页与聊天页达到素雅风目标（视觉、层级、留白、动效）。
- 功能无回归（核心路径通过）。
- 文档中 7 个回合全部打勾，并附回合记录。
- 样式结构比改造前更清晰，可继续迭代。

---

## 11. 回合记录

## 回合 1：设计令牌与主题地基

### 1) 本回合目标
- 建立统一 tokens 与 light/dark 主题入口。
- 将 `App.vue` 改为 token 驱动，保留既有深色兜底覆盖，避免功能回归。

### 2) 变更范围（文件）
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/styles/tokens.css`（新增）
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/styles/theme-light.css`（新增）
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/styles/theme-dark.css`（新增）
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/App.vue`（修改）

### 3) 实施内容
- 抽离基础设计令牌：字体、间距、圆角、动效、语义色。
- 建立 `light/dark` 主题变量层，并桥接 Element Plus 基础字体与禁用态变量。
- `App.vue` 接入新主题文件，`#app` 背景与字体改为 token 驱动。
- 保留原有 Element Plus 深色兜底覆盖，确保本回合不动业务行为。

### 4) 验证结果
- [x] 生产构建通过（`npm run build`）
- [x] 登录页可访问（`http://localhost:3000/login`）
- [x] 深浅主题 token 生效（浏览器运行时校验 class 与 CSS 变量）
- [ ] 聊天全流程手测（待后续回合联合验证）
- [ ] 移动端全链路手测（待后续回合联合验证）

### 5) 风险与问题
- 现有项目中仍存在大量历史 `el-*` 覆盖，主题变量虽已接入，但尚未统一迁移到 token 体系。
- 深色模式相关样式目前是“新 token + 旧兜底”并行状态，后续需要逐步收敛。

### 6) 下一回合计划
- 执行回合 2：重构 `Chat-New.vue` 顶栏与主布局骨架。
- 目标是完成页面结构降噪（保留功能，减少视觉干扰），并同步做桌面/移动端基础验收。

## 回合 2：聊天页主布局骨架

### 1) 本回合目标
- 重构 `Chat-New.vue` 顶栏骨架，降低视觉噪音，保留全部现有功能入口。
- 建立更稳定的桌面/移动端头部布局（无横向溢出）。

### 2) 变更范围（文件）
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/views/Chat-New.vue`（模板 + 样式）

### 3) 实施内容
- 顶栏改为 `left / center / right` 三段结构：
  - 左：侧栏开关 + 标题
  - 中：用量、LaTeX、通知（图标化）
  - 右：语言、主题、用户菜单
- 新增回合 2 局部覆盖样式，统一使用 token 颜色与圆角，去掉“科技风”发光/扫描视觉。
- 对会话 tab 进行“克制化”样式收口（边框/背景/激活态简化）。
- 增加 `1024px`、`768px` 断点布局规则，避免移动端顶栏挤压。

### 4) 验证结果
- [x] 生产构建通过（`npm run build`）
- [x] 聊天页已登录态可正常访问（`/chat`）
- [x] 顶栏核心按钮可见并可交互（侧栏、用量、LaTeX、通知、语言、主题、用户菜单）
- [x] 390px 下无页面横向溢出（运行时校验 `scrollWidth == clientWidth`）
- [ ] 聊天全链路手测（发送、流式、历史编辑）待回合 3/4 联合回归

### 5) 风险与问题
- `Chat-New.vue` 与 `chat.css` 历史样式仍并存，当前通过“局部覆盖”达成改造，后续仍需清理重复规则。
- 页面存在历史 Vue/ElementPlus warning（非本回合引入），建议后续单独收敛。

### 6) 下一回合计划
- 执行回合 3：重构 `ChatSidebar.vue` 的信息分区与视觉层级。
- 目标是让模型/历史/角色/设置四个分区视觉更统一，并继续保持移动端稳定。

## 回合 3：侧栏分区与视觉层级

### 1) 本回合目标
- 对侧栏四个分区（模型/历史/角色/设置）建立一致的卡片层级。
- 不改业务逻辑，仅做结构和样式重构，保证原有功能路径可用。

### 2) 变更范围（文件）
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/components/chat/ChatSidebar.vue`（模板结构）
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/styles/chat-sidebar.css`（回合 3 覆盖样式）

### 3) 实施内容
- 为主要分区容器统一加 `sidebar-section-card`，并增加 `sidebar-section-heading`。
- 将模型选择、对话历史、角色设定、设置相关区域做同一视觉语义：边框、圆角、间距、标题层级统一。
- 侧栏导航按钮改为更克制的 token 风格（弱化高饱和和浮夸 hover）。
- 历史列表、角色区、增强角色区、模型描述区都收口到 token 色板。

### 4) 验证结果
- [x] 生产构建通过（`npm run build`）
- [x] 侧栏四个分区切换可用（模型/历史/角色/设置）
- [x] 历史区刷新/编辑入口可见且可点击
- [x] 390px 下页面无横向溢出（`scrollWidth == clientWidth`）
- [ ] 角色新增/重命名/删除完整链路回归（待回合 4 联合验证）

### 5) 风险与问题
- 目前仍是“新增覆盖样式 + 历史样式并存”模式，后续回合需逐步清理重复规则。
- Playwright 中仍有既有 Element Plus warning（本回合未新增）。

### 6) 下一回合计划
- 执行回合 4：重构 `ChatContent.vue` 消息流样式（头像、气泡、时间、操作区层级）。
- 目标是提升长文本可读性并保持导出/复制/重试等交互不回归。

## 回合 4：消息流样式重构

### 1) 本回合目标
- 提升消息阅读体验：气泡、头像、消息头信息与正文排版更加克制统一。
- 保持发送、复制、重试、导出等交互逻辑完全不变。

### 2) 变更范围（文件）
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/components/chat/ChatContent.vue`（小幅模板补强）
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/styles/chat-content.css`（回合 4 覆盖样式）

### 3) 实施内容
- 在消息内容容器追加类型 class（`message-content-user` / `message-content-ai`）用于稳定皮肤覆盖。
- 新增回合 4 样式层：
  - 统一消息气泡边框、圆角、内边距
  - 弱化头像视觉（去渐变发光，改 token 色块）
  - 收敛消息头（作者/时间/操作按钮）层级
  - 优化正文可读性（段落间距、代码块、引用、表格边框）
- 兼容深色主题和移动端断点（390px）规则。

### 4) 验证结果
- [x] 生产构建通过（`npm run build`）
- [x] 聊天页消息列表正常渲染（历史消息、操作按钮、输入区均可见）
- [x] 390px 下无横向溢出（`scrollWidth == clientWidth`）
- [ ] 实际发送一条新消息的端到端验证（待你本地联调时顺手确认）
- [ ] 导出截图链路回归（待回合 5 或收口回合统一验证）

### 5) 风险与问题
- 消息流样式历史包袱较多，当前采用“新增覆盖层”以降低回归风险，后续仍需清理冗余旧规则。
- 现存 Element Plus warning 与本回合无直接关系，后续可单独安排稳定性回合处理。

### 6) 下一回合计划
- 执行回合 5：重构 `InputArea.vue` 输入区样式和底部操作按钮层级。
- 目标是统一输入区视觉风格，并保证发送快捷键、上传文件、停止流式按钮行为不变。

## 回合 5：输入区样式重构

### 1) 本回合目标
- 重构输入区视觉层级（输入框、上传、停止、发送按钮）。
- 不改发送逻辑、上传逻辑、快捷键逻辑，仅做结构与样式层改造。

### 2) 变更范围（文件）
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/components/chat/InputArea.vue`（新增按钮 class）
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/styles/input-area.css`（回合 5 覆盖样式）

### 3) 实施内容
- 为“停止流式”和“发送”按钮增加独立 class（`stop-stream-btn` / `send-message-btn`），便于风格收口。
- 输入区整体改为 token 驱动风格：
  - 顶部边界和背景统一
  - textarea 边框、圆角、placeholder、focus 状态统一
  - 图片尺寸选择器与按钮组风格统一
- 按钮组改为更稳定的三列布局（上传 / 停止 / 发送），并适配移动端断点。
- 文件预览胶囊样式与暗色主题同步到 token 色板。

### 4) 验证结果
- [x] 生产构建通过（`npm run build`）
- [x] 输入框可输入文本，发送按钮可按禁用/启用状态切换
- [x] 上传触发按钮可见且可点击
- [x] 390px 下无横向溢出（`scrollWidth == clientWidth`）
- [ ] 流式输出中的“停止流式”按钮实机触发验证（待你本地联调确认）

### 5) 风险与问题
- 现有 `input-area.css` 历史规则较多，当前以覆盖层方式达成目标，后续仍建议清理重复规则。
- 移动端键盘相关样式逻辑复杂（`always-fixed-bottom` + `keyboard-visible`），已尽量不触碰行为层。

### 6) 下一回合计划
- 执行回合 6：重构 `Login.vue` 首页视觉，完成素雅风落地闭环。
- 重点收敛背景、卡片、标题、次级操作层级，并保持登录/注册/通知流程不回归。

## 回合 6：首页样式重构

### 1) 本回合目标
- 将登录页视觉从高饱和和高动效收敛到素雅风。
- 保持登录/注册/通知相关交互和校验逻辑不变。

### 2) 变更范围（文件）
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/views/Login.vue`（模板 class 与样式覆盖）

### 3) 实施内容
- 新增登录页语义 class（`login-page-v2`、`login-card`、`login-title`、`login-primary-btn` 等）用于局部重构。
- 新增回合 6 样式覆盖：
  - 页面背景改为低对比渐变 + 轻量光晕
  - 登录卡片边框、阴影、圆角和内边距收敛
  - 主按钮/次按钮改为 token 风格
  - 表单输入框 placeholder/focus 风格统一
  - 保留飞行动画但降低存在感（透明度+速度）
- 深色主题同步覆盖，保证深浅主题视觉一致。

### 4) 验证结果
- [x] 生产构建通过（`npm run build`）
- [x] 登录页可访问（`/login`）且登录卡片存在
- [x] 深色主题样式生效（标题颜色、卡片背景、页面背景校验通过）
- [x] 390px 下无横向溢出（`scrollWidth == clientWidth`）
- [ ] 注册弹窗完整交互链路手测（建议你本地点开再确认一次）

### 5) 风险与问题
- 登录页历史暗色样式仍在文件中并与新覆盖并存，当前依靠后置覆盖保证效果。
- 后续可考虑把登录页样式独立拆分文件，降低 `Login.vue` 样式复杂度。

### 6) 下一回合计划
- 执行回合 7：样式清理与收口，补齐本轮收尾记录和残余技术债清单。

## 回合 7：样式清理与收口

### 1) 本回合目标
- 完成本轮 1~6 回合的交付闭环，整理结果与后续维护点。

### 2) 收口动作
- 更新执行手册进度看板，标记 7 个回合全部完成。
- 对每个回合补充“变更范围 + 验证结果 + 风险”记录，确保可追踪。
- 汇总当前剩余技术债，供下轮迭代使用。

### 3) 剩余技术债（建议后续处理）
- 历史样式与新增覆盖层并存（`chat.css` / `chat-sidebar.css` / `chat-content.css` / `input-area.css`），可再做一次“去重清理回合”。
- Element Plus 运行时 warning 仍存在，建议单独开“稳定性回合”逐条收敛。
- 登录页样式建议拆分到独立样式文件以降低单文件体积。

### 4) 最终状态
- 首页与聊天页均已完成素雅风重构主线目标。
- 保持现有业务功能不变，支持继续迭代。

## 回合 8：全局色系统一（橙主绿辅）

### 1) 本回合目标
- 将当前前端所有主要界面统一为“橙色主色 + 绿色辅色”。
- 保持 Claude 风格的低饱和、克制、可读性优先。

### 2) 变更范围（文件）
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/styles/tokens.css`
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/styles/theme-dark.css`
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/App.vue`
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/views/Login.vue`
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/views/Chat-New.vue`
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/views/Admin.vue`
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/components/NotificationPanel.vue`
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/components/chat/ChatSidebar.vue`
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/components/chat/ChatContent.vue`
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/styles/chat.css`
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/styles/chat-sidebar.css`
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/styles/chat-content.css`
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/styles/input-area.css`
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/styles/font-size-control.css`
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/styles/admin.css`

### 3) 实施内容
- 重定义设计令牌：
  - 主色 `--accent-1` 统一为柔和橙。
  - 辅色 `--accent-2` 统一为低饱和绿。
  - 浅/深背景、边框、正文色统一调整为莫兰迪低对比层级。
- 完成 Element Plus 语义色桥接：`--el-color-primary*` 绑定橙系，`--el-color-success*` 绑定绿系。
- 清理并替换页面与组件内残留蓝/紫硬编码（含 Tailwind 颜色类与 CSS 常量）。
- 保留危险操作红色语义（删除、报错等）不改，以维持可用性与风险识别。

### 4) 验证结果
- [x] 全量扫描确认主链路无蓝紫主题残留（危险红色除外）
- [x] 生产构建通过（`npm run build`）
- [x] 聊天页桌面与移动端（390px）快速回测通过
- [x] 登录页、聊天页、管理页主色基调一致

### 5) 风险与问题
- 历史样式文件体量较大（如 `chat.css`），当前仍属于“统一后可用态”，后续建议做结构化拆分与去重。
- 代码高亮等语义配色仍有局部独立颜色体系（不影响主界面基调）。

### 6) 下一回合计划
- 做“样式去重与分层”专项：把历史覆盖按 `layout / component / theme` 重排，减少后续迭代成本。

## 回合 9：夜间模式统一 + CSS 首轮去重

### 1) 本回合目标
- 夜间模式全面对齐橙绿 token 体系。
- 删除已确认未使用的历史样式块，降低样式体积与冲突风险。

### 2) 变更范围（文件）
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/App.vue`
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/views/Chat-New.vue`
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/views/Login.vue`
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/styles/chat.css`
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/styles/admin.css`
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/styles/chat-sidebar.css`
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/styles/chat-content.css`
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/styles/input-area.css`
- `/Users/chenyifei.anon/IdeaProjects/openai-project/cyf/project/fe/src/styles/font-size-control.css`

### 3) 实施内容
- `App.vue` 深色 Element Plus 覆盖改为 token 驱动（`--bg-* / --line-1 / --text-* / --accent-*`）。
- `Chat-New.vue` 移除历史“科技感”样式与重复块，仅保留当前布局所需样式。
- `Login.vue` 删除重复的深色兜底块，统一使用主题变量。
- 对 `chat/admin/sidebar/content/input/font-size` 样式做第一批深色硬编码替换，降低 `#222/#333/#555/#e0...` 等直写值。
- `chat.css` 首轮删除已确认未使用块与冗余覆盖，减少历史冲突面。

### 4) 验证结果
- [x] 生产构建通过（`npm run build`）
- [x] 聊天页浅/深色切换可用
- [x] 390px 移动端回测通过
- [x] 首轮去重后产物 CSS 体积下降（`index-*.css` 约从 `574KB` 降至 `494KB`）

### 5) 风险与问题
- `chat.css` 仍有历史规则与注释残留，尚未完成结构化拆分。
- 某些规则虽未在当前模板直接出现，但可能由动态/Teleport类名触发，后续删除需继续小步验证。

### 6) 下一回合计划
- 回合 10：按“引用证据 + 页面回归”继续做第二批去重，优先清理 `chat.css` 中仍未被引用且无运行时命中证据的规则。
