#!/bin/bash
# 开发环境启动脚本 - 同时启动前端和后端

set -e

# 函数：终止占用指定端口的进程
kill_port() {
    local port=$1
    local pid=$(lsof -ti:$port)
    if [ -n "$pid" ]; then
        echo "⚠️  端口 $port 被占用，正在终止进程 $pid..."
        kill -9 $pid
        sleep 1
    fi
}

# 清理占用端口的进程
echo "🧹 清理占用的端口..."
kill_port 3000   # 前端端口
kill_port 39997  # 后端端口

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 启动开发环境..."

# 全局变量存储子进程PID
BACKEND_PID=""
FRONTEND_PID=""

# 设置退出信号处理，以便优雅地关闭所有子进程
cleanup() {
    echo ""
    echo "🛑 正在停止开发环境..."

    # 终止前端进程（如果存在）
    if [[ -n $FRONTEND_PID ]] && kill -0 $FRONTEND_PID 2>/dev/null; then
        echo "🛑 终止前端进程 ($FRONTEND_PID)..."
        kill $FRONTEND_PID 2>/dev/null
    fi

    # 终止后端进程（如果存在）
    if [[ -n $BACKEND_PID ]] && kill -0 $BACKEND_PID 2>/dev/null; then
        echo "🛑 终止后端进程 ($BACKEND_PID)..."
        kill $BACKEND_PID 2>/dev/null
    fi

    # 给予进程一些时间来优雅关闭
    sleep 2

    # 如果还有进程没关闭，则强制终止
    if [[ -n $FRONTEND_PID ]]; then
        kill -9 $FRONTEND_PID 2>/dev/null || true
    fi

    if [[ -n $BACKEND_PID ]]; then
        kill -9 $BACKEND_PID 2>/dev/null || true
    fi

    # 最后备选方案：根据端口终止进程
    pkill -f "python.*server.py" 2>/dev/null || true
    pkill -f "npm.*run.*dev" 2>/dev/null || true
    pkill -f "vite" 2>/dev/null || true

    sleep 1
    # 再次强制终止可能残留的进程
    lsof -ti:3000 | xargs kill -9 2>/dev/null || true
    lsof -ti:39997 | xargs kill -9 2>/dev/null || true

    echo "👋 开发环境已停止"
    exit 0
}

# 捕获退出信号
trap cleanup INT TERM

# 启动后端服务（在后台运行）
echo "🔌 启动后端服务..."
cd "$PROJECT_ROOT/cyf/project/server" && python server.py &
BACKEND_PID=$!

# 给后端一些时间来启动
sleep 3

# 检查后端是否成功启动
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "❌ 后端服务启动失败"
    exit 1
fi

# 启动前端服务（也在后台运行，以便我们能捕获其PID并控制它）
echo "🌐 启动前端服务..."
cd "$PROJECT_ROOT/cyf/project/fe" && npm run dev &
FRONTEND_PID=$!

# 检查前端是否成功启动
if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    echo "❌ 前端服务启动失败"
    cleanup
    exit 1
fi

echo "✅ 前后端服务已启动 (前端 PID: $FRONTEND_PID, 后端 PID: $BACKEND_PID)"
echo "💡 按 Ctrl+C 退出并停止所有服务"

# 等待前端和后端进程结束
wait $FRONTEND_PID $BACKEND_PID 2>/dev/null