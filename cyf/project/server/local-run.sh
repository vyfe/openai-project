#!/bin/bash
# 后端本地启动脚本
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$SCRIPT_DIR"

# 检查并终止占用 39997 端口的进程
PORT=39997
PID=$(lsof -ti:$PORT)
if [ -n "$PID" ]; then
    echo "⚠️  端口 $PORT 被占用，正在终止进程 $PID..."
    kill -9 $PID
    sleep 1
fi

# 激活虚拟环境
if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
    source "$PROJECT_ROOT/.venv/bin/activate"
else
    echo "警告: 虚拟环境不存在 $PROJECT_ROOT/.venv，使用系统 Python"
fi

# 检查依赖
if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
    pip install -r "$PROJECT_ROOT/requirements.txt" -q
else
    echo "警告: 未找到 requirements.txt 文件"
fi

# 启动服务
echo "🚀 启动后端服务，监听端口 $PORT..."
python server.py