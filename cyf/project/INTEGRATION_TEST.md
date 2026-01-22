# 前后端集成测试说明

## 运行系统
运行前需要确认当前的目录，再觉得是否执行后续的进入目录步骤。
### 启动后端服务
1. 进入后端目录: `cd cyf/project/server`
2. 确保已安装依赖: `pip install flask openai requests peewee`
3. 启动服务: `python server.py &`
4. 服务将运行在 http://localhost:39997

### 启动前端服务
1. 进入前端目录: `cd cyf/project/fe`
2. 安装依赖: `npm install`
3. 启动开发服务器: `npm run dev`
4. 前端将运行在 http://localhost:5173

## 验证集成

### API 测试
您可以使用curl命令测试API连接:

```bash
# 测试连接
curl -X POST http://localhost:39997/never_guess_my_usage/test -d "user=test_user"

# 文件上传测试（示例）
curl -X POST -F "file=@test.txt" http://localhost:39997/never_guess_my_usage/download
```

### 功能验证
1. 用户登录：前端会向后端验证用户名是否在允许列表中
2. 模型选择：前端支持GPT-4o mini、GPT-4o、GPT-4o-all、GPT-3.5-turbo、图像生成等模型
3. 聊天功能：前端发送消息到 `/never_guess_my_usage/split` 接口
4. 图像生成功能：前端发送请求到 `/never_guess_my_usage/split_pic` 接口
5. 对话历史：前端通过 `/never_guess_my_usage/split_his` 和 `/never_guess_my_usage/split_his_content` 获取历史记录
6. 文件上传：前端通过 `/never_guess_my_usage/download` 上传文件

## 配置说明
- 后端服务运行在39997端口
- 前端通过 http://localhost:39997 与后端通信
- 需要在 conf/conf.ini 中配置有效的API密钥和允许的用户名
- 支持的文件上传格式：txt, pdf, png, jpg, jpeg, gif, ppt, pptx

## 故障排除
如果遇到连接问题：
1. 确认后端服务是否运行在39997端口
2. 检查防火墙设置
3. 确认用户名是否在配置文件的允许列表中
4. 检查API密钥是否有效