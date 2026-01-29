# 修复 Chat-New.vue 缺失逻辑计划

## 背景

Chat-New.vue 是对 Chat.vue 的组件化重构版本，将功能拆分为 `ChatSidebar.vue` 和 `ChatContent.vue`，以及 `useChat.ts` composable。但在重构过程中，大量核心功能丢失。

## 缺失功能清单

### 1. Header 区域 (Chat-New.vue 主文件)

| 功能 | 状态 | 说明 |
|------|------|------|
| 用户信息显示 | ❌ 缺失 | 需添加 `authStore.user` 显示 |
| 用量查询弹窗 | ❌ 不完整 | 有 UI 但无实际 API 调用 (fetchUsage) |
| LaTeX 帮助按钮 | ❌ 缺失 | 弹窗内容为空 |
| 侧边栏切换图标 | ❌ 不一致 | 应使用 Expand/Fold 而非 Menu |

### 2. Sidebar 区域 (ChatSidebar.vue)

| 功能 | 状态 | 说明 |
|------|------|------|
| 模型列表 API | ❌ 缺失 | 硬编码的选项，应从 API 加载 |
| 厂商选择器 | ❌ 缺失 | 无厂商筛选逻辑 |
| 模型推荐标签 | ❌ 缺失 | 无推荐模型标识 |
| 对话历史 API | ❌ 缺失 | 模拟数据，应从 API 加载 |
| 批量删除功能 | ❌ 缺失 | 无编辑模式和批量删除 |
| 增强角色系统 | ❌ 缺失 | 无增强角色 UI 和 API |
| 自定义角色管理 | ❌ 缺失 | 无添加/重命名/删除角色 |
| localStorage 持久化 | ❌ 不完整 | 状态未持久化 |
| Tooltip 超长文本 | ❌ 缺失 | 无溢出提示 |

### 3. Content 区域 (ChatContent.vue)

| 功能 | 状态 | 说明 |
|------|------|------|
| sendMessage API | ❌ 缺失 | useChat 只有模拟实现 |
| 流式输出 | ❌ 缺失 | 无 SSE/流式处理逻辑 |
| KaTeX 渲染 | ❌ 缺失 | 无 LaTeX 公式渲染 |
| 消息复制 | ❌ 缺失 | 无复制按钮和功能 |
| 消息删除 | ❌ 缺失 | 无删除功能 |
| 错误重试 | ❌ 缺失 | 无重试按钮 |
| 继续生成 | ❌ 缺失 | 无截断继续生成 |
| 文件上传 API | ❌ 不完整 | UI 存在但无实际上传 |
| 导出截图 | ❌ 缺失 | 无 html2canvas 集成 |
| 回到顶部 | ❌ 缺失 | 无滚动到顶部按钮 |
| 水印/链接 | ❌ 缺失 | 无版权水印和 GitHub 链接 |
| 流式动画 | ❌ 缺失 | 无打字动画效果 |
| 图像生成 API | ❌ 缺失 | 无 DALL-E 等图像生成支持 |

### 4. 样式问题

| 问题 | 说明 |
|------|------|
| chat.css 未引用 | Chat-New.vue 未导入 `@/views/styles/chat.css` |
| 深色主题不完整 | 缺少 body.dark-theme 相关样式 |
| 移动端响应式 | 样式不完整 |

### 5. useChat.ts Composable

| 问题 | 说明 |
|------|------|
| API 集成缺失 | sendMessage 只是模拟，未调用 chatAPI |
| 流式处理缺失 | 无 sendChatStream 支持 |
| KaTeX 未集成 | renderMarkdown 无 LaTeX 支持 |
| 对话上下文构建 | 无 buildDialogArrayFromSnapshot 逻辑 |

---

## 完整修复计划

### 阶段 1: 基础设施修复

#### 1.1 重写 useChat.ts Composable
```typescript
// 需要添加的导入
import { chatAPI, fileAPI } from '@/services'
import katex from 'katex'

// 需要实现的函数
- sendMessage(): 支持流式/非流式，调用 chatAPI.sendChat/sendChatStream
- loadDialogContent(): 调用 chatAPI.getDialogContent
- buildDialogArrayFromSnapshot(): 构建对话上下文
- renderMarkdownWithMath(): KaTeX + Markdown 渲染
- extractFileUrls(): 从消息中提取文件URL
- getTextContent(): 获取纯文本内容
- isImageUrl(): 判断URL是否为图片
```

#### 1.2 扩展 types.ts
```typescript
// 需要添加的类型
- DialogHistoryItem: 对话历史项（与API响应匹配）
- UsageData: 用量数据
- EnhancedRole: 增强角色
- EnhancedRoleGroup: 角色分组
- RolePreset: 角色预设
```

### 阶段 2: ChatSidebar.vue 完整实现

#### 2.1 模型选择器
- 调用 API 获取模型列表 (onMounted)
- 实现厂商选择器（从模型列表提取厂商）
- 实现模型筛选逻辑
- 显示模型描述和推荐标签
- 级联选择器支持

#### 2.2 对话历史
- loadDialogHistory(): 从 API 加载
- loadDialogContent(): 加载特定对话
- confirmSingleDelete(): 单个删除
- confirmBatchDelete(): 批量删除
- enterEditMode/exitEditMode: 编辑模式
- Tooltip 溢出文本显示

#### 2.3 角色系统
- 预设角色选项卡 (default/programmer/translator/writer)
- 自定义角色添加/重命名/删除
- 增强角色系统:
  - loadEnhancedRoles(): 从 API 加载
  - 分组标签 (el-tabs)
  - 角色单选列表 (el-radio)
  - 角色预览

#### 2.4 设置持久化
- watch 监听器保存到 localStorage
- onMounted 时从 localStorage 恢复

### 阶段 3: ChatContent.vue 完整实现

#### 3.1 工具栏
- 对话标题编辑器 + 更新按钮
- 字体大小控制 (small/medium/large)
- 开启新会话按钮
- 导出截图按钮 (html2canvas)
- 移动端抽屉菜单

#### 3.2 消息列表
- Markdown + KaTeX 渲染
- 图片/文件附件显示
- 消息操作按钮 (复制/删除)
- 流式输出动画 (typing dots)
- 错误消息 + 重试按钮
- 截断消息 + 继续生成按钮
- 空响应提示

#### 3.3 输入区域
- 文件上传 (调用 fileAPI.upload)
- 键盘快捷键 (Enter/Ctrl+Enter)
- 发送按钮禁用状态

#### 3.4 其他功能
- 回到顶部按钮 (showBackToTop, scrollToTop)
- 水印和 GitHub 链接
- 图片预览对话框
- 滚动事件处理 (isScrolledToBottom)

### 阶段 4: Chat-New.vue 主文件完善

#### 4.1 Header
- 用户信息显示 (authStore.user)
- 用量查询弹窗 (fetchUsage, usageData, loadingUsage)
- LaTeX 帮助弹窗内容
- 侧边栏切换图标 (Expand/Fold)

#### 4.2 样式导入
```vue
<style scoped>
@import '@/views/styles/chat.css';
@import 'highlight.js/styles/github-dark.css';
@import 'katex/dist/katex.min.css';
</style>
```

### 阶段 5: 路由切换

修改 `/cyf/project/fe/src/router/index.ts`:
```typescript
// 将 Chat-New 设为默认聊天页面
{
  path: '/chat',
  name: 'Chat',
  component: () => import('@/views/Chat-New.vue')
}
```

---

## 关键文件清单

| 文件 | 操作 |
|------|------|
| `/cyf/project/fe/src/views/Chat-New.vue` | 修改 |
| `/cyf/project/fe/src/components/chat/ChatSidebar.vue` | 修改 |
| `/cyf/project/fe/src/components/chat/ChatContent.vue` | 修改 |
| `/cyf/project/fe/src/composables/useChat.ts` | 重写 |
| `/cyf/project/fe/src/components/chat/types.ts` | 扩展 |
| `/cyf/project/fe/src/router/index.ts` | 修改 (最后切换路由) |

---

## 验证计划

1. **本地启动**：`npm run dev` 验证无编译错误
2. **登录测试**：验证用户登录和信息显示
3. **模型选择**：验证模型列表从 API 加载
4. **发送消息**：测试流式/非流式消息发送
5. **对话历史**：测试加载、删除对话
6. **用量查询**：测试用量 API 调用
7. **主题切换**：验证深色/浅色主题
8. **移动端**：验证响应式布局
