# 更新对话标题功能实现

## 概述
为对话系统添加了更新对话标题的功能，包括后端API接口和前端UI组件。

## 后端更改

### 1. 数据库层 - `sqlitelog.py`
- 添加了 `update_dialog_title(user: str, dialog_id: int, new_title: str) -> bool` 函数
- 该函数负责在数据库中更新特定对话的标题

### 2. API层 - `server.py`
- 添加了 `/never_guess_my_usage/update_dialog_title` 端点
- 实现了身份验证、参数验证和错误处理
- 确保只有对话的所有者才能更新对话标题

## 前端更改

### 1. API服务 - `api.ts`
- 在 `chatAPI` 对象中添加了 `updateDialogTitle` 方法
- 该方法封装了对后端API的调用

### 2. UI组件 - `Chat.vue`
- 添加了 `currentDialogId` 响应式变量来跟踪当前对话ID
- 添加了 `titleFocused` 变量来跟踪标题输入框的焦点状态
- 修改了 `loadDialogContent` 函数，在加载对话时设置当前对话ID
- 修改了 `clearCurrentSession` 函数，在清空会话时重置对话ID
- 添加了 `updateDialogTitle` 函数来处理标题更新请求
- 在桌面端和移动端的标题编辑区域添加了更新按钮
- 添加了相应的CSS样式

## 功能特性

### 后端
- 安全的身份验证和权限控制
- 参数验证和错误处理
- 数据库操作的异常处理

### 前端
- 用户友好的界面，当标题输入框获得焦点时显示更新按钮
- 实时反馈和错误提示
- 与现有对话历史的同步

## 使用流程

1. 用户打开已有对话
2. 点击标题输入框以获得焦点
3. 输入新的标题内容
4. 点击"更新标题"按钮
5. 系统验证用户权限并更新数据库中的标题
6. 前端收到成功响应并显示确认消息

## API接口

### 更新对话标题
- **URL**: `POST /never_guess_my_usage/update_dialog_title`
- **参数**:
  - `user`: 用户名
  - `password`: 用户密码
  - `dialog_id`: 对话ID
  - `new_title`: 新标题
- **响应**:
  ```json
  {
    "success": true,
    "msg": "对话标题更新成功"
  }
  ```

## 错误处理

- 当用户没有权限时返回错误
- 当对话ID不存在时返回错误
- 当参数缺失时返回错误
- 前端显示相应的错误消息

## 测试

包含一个HTML测试页面 (`test_update_dialog.html`) 来直接测试API端点。