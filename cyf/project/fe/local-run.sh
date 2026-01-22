#!/bin/bash

# 前端本地启动脚本
# 使用方法: ./local-run.sh 或 bash local-run.sh

# 获取脚本所在目录，确保从任何位置运行都能正确切换到前端目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查并终止占用 3000 端口的进程
PORT=3000
PID=$(lsof -ti:$PORT)
if [ -n "$PID" ]; then
    echo "⚠️  端口 $PORT 被占用，正在终止进程 $PID..."
    kill -9 $PID
    sleep 1
fi

echo "🚀 启动前端开发服务器..."
echo "📁 工作目录: $SCRIPT_DIR"

# 检查node_modules是否存在，不存在则安装依赖
if [ ! -d "node_modules" ]; then
    echo "📦 首次运行，正在安装依赖..."
    npm install
fi

echo "✅ 启动 Vite 开发服务器 (http://localhost:3000)"
npm run dev