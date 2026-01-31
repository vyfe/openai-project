# Python OpenAI 客户端-服务端项目

## 项目概述

这是一个基于Python的OpenAI API客户端-服务端项目，提供了图形用户界面客户端和后端服务，支持多种OpenAI模型（包括GPT系列和DALL-E图像生成）。项目还包括一个现代化的Vue前端界面，用于更好的用户体验。

## CSS样式管理规范

为保持代码一致性和可维护性，项目新增功能均需遵循以下CSS样式管理规范：

1. **样式集中管理**：
   - 组件独有样式应整理到独立的CSS文件中（如`chat-sidebar.css`）
   - 通过`@import`方式在组件中引用外部CSS文件
   - 避免在组件内部编写大量内联样式

2. **使用Tailwind v4进行开发**：
   - 新增功能必须使用Tailwind v4的实用优先的CSS类名
   - 通过Tailwind类名实现响应式设计和主题切换
   - 遵循Tailwind的设计系统原则，保持UI一致性

3. **CSS与Tailwind混合使用指南**：
   - 对于Element Plus等第三方组件的样式定制，保留必要的CSS（使用`:deep()`选择器）
   - 一般样式布局优先使用Tailwind类名
   - 复杂的动画或特殊效果可使用CSS实现

4. **响应式设计**：
   - 使用Tailwind的响应式前缀（如`md:`, `lg:`等）实现多断点适配
   - 遵活运用Flexbox和Grid布局类名

5. **主题支持**：
   - 使用Tailwind的dark mode变体（如`dark:bg-gray-800`）
   - 确保所有UI元素在亮色和暗色主题下都有良好的视觉效果

## 项目结构

```
cyf/
└── project/
    ├── client/          # 旧版客户端代码（Python/Tkinter）
    │   ├── client.py        # 主客户端界面 (使用CustomTkinter)
    │   ├── client_support.py # 客户端支持功能
    │   ├── client_pack.py   # 客户端打包脚本
    │   └── conf/            # 客户端配置
    ├── fe/              # 新版前端代码（Vue/TypeScript）
    │   ├── src/             # 源代码目录
    │   │   ├── components/  # 组件目录
    │   │   ├── pages/       # 页面目录
    │   │   ├── services/    # API服务目录
    │   │   ├── stores/      # 状态管理目录
    │   │   ├── router/      # 路由配置目录
    │   │   └── views/       # 视图组件目录
    │   ├── public/          # 静态资源目录
    │   ├── package.json     # 项目依赖配置
    │   ├── vite.config.ts   # 构建配置
    │   └── tsconfig.json    # TypeScript配置
    └── server/          # 服务端代码
        ├── server.py        # 主服务端应用 (Flask)
        ├── server_pack.py   # 服务端打包脚本
        ├── sqlitelog.py     # SQLite日志记录模块
        ├── deploy.sh        # 部署脚本
        └── conf/            # 服务端配置
            ├── conf.ini.tpl # 服务端配置模板
            └── uwsgi.ini    # uWSGI配置文件
```

## 功能特性

### 服务端 (server/)
- 基于Flask的Web API服务
- 支持多API密钥轮询负载均衡
- 支持多种OpenAI模型：
  - GPT-4o mini
  - GPT-4o
  - GPT-4o-all
  - GPT-3.5-turbo
  - DALL-E 图像生成
- 文件上传功能 (支持 txt, pdf, png, jpg, jpeg, gif, ppt, pptx)
- SQLite数据库日志记录系统
  - 记录用户请求、用量、模型使用情况
  - 记录对话历史和上下文
- 使用uWSGI部署，支持多进程和线程

### 前端 (fe/)
- 基于Vue 3和TypeScript的现代化Web界面
- 用户身份验证
- 模型选择器 (GPT-4o, GPT-3.5-turbo, DALL-E等)
- 聊天对话界面，支持实时消息流
- 对话历史管理
- 文件上传功能（支持多种格式）
- 响应式设计，适配不同屏幕尺寸
- Element Plus UI组件库
- 在Vue组件中使用 `:deep()` 选择器可以穿透作用域样式修改第三方组件样式
- 针对 `<pre>` 和 `<code>` 标签设置 `max-width: 100%` 和 `overflow-x: auto` 防止内容溢出
- 使用 `white-space: pre-wrap` 保持代码格式的同时允许换行
- 使用 `table-layout: fixed` 确保表格在小屏幕上布局稳定
- 使用 `word-break: break-word` 和 `overflow-wrap: break-word` 确保长内容能正确换行

### 客户端 (client/) - 旧版
- 基于CustomTkinter的图形用户界面
- 用户身份验证
- 模型选择器 (GPT-4o, GPT-3.5-turbo, DALL-E等)
- 聊天对话界面
- 对话历史管理
- 文件上传功能
- 服务器选择和版本信息显示

## 配置说明

### 服务端配置 (conf/conf.ini)
- `common.upload_dir`: 上传文件存储目录
- `common.users`: 允许访问的用户名列表
- `log.sqlite3_file`: SQLite日志数据库文件路径
- `api.api_key`: OpenAI API密钥
- `api.api_host`: OpenAI API主机地址
- `model.*`: 各种模型的映射名称

### 部署方式
- 使用uWSGI运行Flask应用
- 监听端口39997
- 可配置多个工作进程(默认5个)和线程(默认2个)
- Vue前端通过Vite构建，可部署为静态资源

## 技术栈

### 服务端
- Python 3
- Flask (Web框架)
- OpenAI Python SDK
- Requests (HTTP请求)
- Peewee (SQLite ORM)
- uWSGI (应用服务器)

### 前端 (新)
- Vue 3 (UI框架)
- TypeScript (语言)
- Vite (构建工具)
- Element Plus (UI组件库)
- Pinia (状态管理)
- Axios (HTTP客户端)

### 客户端 (旧)
- Python 3
- CustomTkinter (GUI框架)
- Tkinter (基础GUI)
- Requests (与服务端通信)
- OpenAI Python SDK

## 数据库模型

### Log 表
- `username`: 用户名
- `modelname`: 模型名称
- `usage`: 用量
- `request_text`: 请求文本内容

### Dialog 表
- `username`: 用户名
- `chattype`: 对话类型
- `modelname`: 模型名称
- `dialog_name`: 对话名称
- `start_date`: 开始日期
- `context`: 对话上下文

## 部署说明

### 服务端部署
1. 将项目文件复制到服务器
2. 配置环境变量和依赖
3. 修改 `conf/conf.ini` 中的API密钥和其他设置
4. 运行 `deploy.sh` 脚本启动服务
5. 服务将在39997端口监听

### 前端部署
1. 进入 `cyf/project/fe` 目录
2. 执行 `npm install` 安装依赖
3. 执行 `npm run build` 构建生产版本
4. 将生成的 `dist` 目录部署到Web服务器

### 开发模式启动
1. 启动服务端：`cd cyf/project/server && python server.py`
2. 启动前端：`cd cyf/project/fe && npm run dev`

## 快速启动脚本

项目提供了便捷的本地启动脚本，可从任意目录运行：

### 启动后端
```bash
# 方式1：直接运行脚本
./cyf/project/server/local-run.sh

# 方式2：使用bash运行
bash cyf/project/server/local-run.sh
```

后端将在 http://localhost:39997 启动。

### 启动前端
```bash
# 方式1：直接运行脚本
./cyf/project/fe/local-run.sh

# 方式2：使用bash运行
bash cyf/project/fe/local-run.sh
```

前端将在 http://localhost:3000 启动。

### 同时启动前后端（推荐用于开发）
```bash
# 方式1：直接运行脚本
./start-dev.sh

# 方式2：使用bash运行
bash start-dev.sh
```

此脚本会自动：
- 检查并清理占用 3000（前端）和 39997（后端）端口的进程
- 启动后端服务（后台运行）
- 启动前端服务（前台运行，便于查看日志）
- 支持优雅退出（按 Ctrl+C 同时停止前后端服务）

### 开发模式启动
1. 启动服务端：`cd cyf/project/server && python server.py`
2. 启动前端：`cd cyf/project/fe && npm run dev`

## 安全考虑

- 用户认证通过配置文件中的用户列表进行控制
- 支持限制文件上传类型，防止恶意文件上传
- 使用SQLite进行访问日志记录以便审计
- 前端不存储敏感信息，与后端通过API通信

## 注意事项

- 需要有效的OpenAI API密钥才能使用
- 客户端和服务端之间通过HTTP协议通信
- 支持负载均衡，可配置多个API端点
- 日志记录所有用户交互和用量统计
- **关键运行说明**：服务端必须在 `cyf/project/server` 目录中运行，因为代码使用相对路径 `conf/conf.ini` 来加载配置文件
- 前端通过 `http://localhost:39997` 访问后端API
- CSS样式都通过tailwind4进行管理

## 关键运行说明
- 服务端必须在 `cyf/project/server` 目录中运行，因为代码使用相对路径 `conf/conf.ini` 来加载配置文件
- 启动前端开发服务器时，确保后端服务在 http://localhost:39997 可用
- 多进程 uWSGI 部署时注意共享资源的并发访问问题

## API 密钥安全最佳实践
- 在生产环境中使用环境变量而不是硬编码 API 密钥
- 定期轮换 API 密钥并监控用量
- 在 conf/conf.ini 文件中使用安全权限保护密钥文件

## 前后端分离开发注意事项
- 前端通过 http://localhost:39997 访问后端 API，在开发环境中需确保该地址可达
- 跨域资源共享 (CORS) 配置已在 Flask 应用中启用
- 前端开发时可通过代理配置解决跨域问题

## 移动端开发注意事项
- 处理窗口大小变化时要区分初始化检测和动态调整，避免在软键盘弹出/收起时触发不必要的UI状态变更
- resize事件中不要无条件更改侧边栏折叠状态，应该对比变化前后状态再决定是否更新UI
- 检测移动设备时，记录设备类型的变化状态以防止重复操作
- 在处理移动端代码块和表格布局时，使用 `white-space: pre-wrap` 保持代码格式的同时允许换行
- 使用 `table-layout: fixed` 确保表格在小屏幕上布局稳定
- 针对 `<pre>` 和 `<code>` 标签设置 `max-width: 100%` 和 `overflow-x: auto` 防止内容溢出
- 移动端媒体查询常用断点: `(max-width: 768px)` 和 `(max-width: 480px)`
- 使用 `word-break: break-word` 和 `overflow-wrap: break-word` 确保长内容能正确换行
- Element Plus 组件在移动端需要特殊的间距和尺寸调整
- 在Vue组件中使用 `:deep()` 选择器可以穿透作用域样式修改第三方组件样式