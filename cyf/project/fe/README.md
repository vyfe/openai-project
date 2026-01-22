# Vue LLM Chat - 智能对话系统

一个基于Vue 3 + TypeScript + Element Plus构建的智能对话系统，支持用户登录、文件上传、模型选择和AI对话功能。

## 🎨 项目特色

- **现代化UI设计**：采用黄绿色系配色，界面清新优雅
- **完整的用户认证**：登录/登出功能
- **文件上传支持**：支持txt、pdf、doc、docx、jpg、jpeg、png格式
- **多模型选择**：支持GPT-3.5 Turbo、GPT-4、文心一言、通义千问
- **实时对话**：流畅的聊天体验，支持打字效果
- **响应式设计**：适配不同屏幕尺寸

## 🛠️ 技术栈

- **前端**：Vue 3 + TypeScript + Vite
- **UI框架**：Element Plus + 自定义样式
- **状态管理**：Pinia
- **路由**：Vue Router
- **HTTP客户端**：Axios
- **后端**：Node.js + Express（模拟API）
- **文件上传**：Multer

## 📦 安装依赖

```bash
# 安装前端依赖
npm install

# 安装后端依赖
npm install express cors multer
```

## 🚀 快速开始

### 1. 启动后端服务
```bash
node server.js
```
后端服务将运行在 http://localhost:3001

### 2. 启动前端开发服务器
```bash
npm run dev
```
前端应用将运行在 http://localhost:3000

### 3. 构建生产版本
```bash
npm run build
```

## 📋 功能说明

### 登录功能
- 用户名：任意3个以上字符
- 密码：任意6个以上字符
- 登录成功后会自动跳转到聊天页面

### 聊天功能
1. **模型选择**：在左侧边栏选择不同的AI模型
2. **文件上传**：支持拖拽或点击上传文件
3. **发送消息**：输入问题后按Enter或点击发送按钮
4. **查看回复**：AI会返回基于所选模型的智能回复

### 支持的文件类型
- 文档：txt、pdf、doc、docx
- 图片：jpg、jpeg、png
- 文件大小限制：10MB

## 🔧 API接口

### 用户登录
- **POST** `/api/login`
- 参数：{ username, password }
- 返回：{ success, message, data: { token, user } }

### 文件上传
- **POST** `/api/upload`
- 参数：FormData（file字段）
- 返回：{ success, message, data: { filename, originalname, size, path } }

### AI对话
- **POST** `/api/chat`
- 参数：{ message, model, file? }
- 返回：{ success, message, data: { response, model, timestamp } }

### 获取模型列表
- **GET** `/api/models`
- 返回：{ success, message, data: [ { label, value } ] }

## 🎨 设计特点

### 配色方案
- 主色调：#9acd32（黄绿色）
- 辅助色：#7dd87d（浅绿色）
- 背景色：线性渐变（#f9f7f0 到 #e8f5e8）
- 文字色：#5a8a5a（深绿色）

### 视觉效果
- 毛玻璃效果（backdrop-filter）
- 圆角设计（border-radius）
- 阴影效果（box-shadow）
- 动画效果（打字动画、悬停效果）

## 📱 响应式设计

- 桌面端：完整的侧边栏和功能展示
- 平板端：自适应布局
- 移动端：优化的触摸体验

## 🔒 安全特性

- JWT Token认证
- 路由守卫
- 文件类型验证
- 文件大小限制
- XSS防护

## 📝 开发说明

### 项目结构
```
vue-llm-chat/
├── src/
│   ├── components/     # 公共组件
│   ├── views/         # 页面组件
│   ├── stores/        # 状态管理
│   ├── services/      # API服务
│   ├── router/        # 路由配置
│   └── main.ts        # 入口文件
├── server.js          # 后端服务
├── package.json       # 项目配置
└── vite.config.ts     # Vite配置
```

### 开发建议
1. 使用TypeScript进行类型检查
2. 遵循Vue 3 Composition API规范
3. 使用Element Plus组件库
4. 保持代码风格一致性

## 🤝 贡献指南

欢迎提交Issue和Pull Request来改进项目。

## 📄 许可证

MIT License

## 🆘 常见问题

### Q: 无法启动项目？
A: 请确保已安装Node.js和npm，然后重新安装依赖。

### Q: 文件上传失败？
A: 检查文件格式是否在支持列表中，文件大小是否超过10MB限制。

### Q: 登录后无法访问聊天页面？
A: 检查浏览器localStorage是否正确存储了token，或尝试重新登录。

## 📞 联系方式

如有问题，请通过GitHub Issue联系。