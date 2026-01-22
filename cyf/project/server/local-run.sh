#!/bin/bash
# 后端本地启动脚本
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$SCRIPT_DIR"

# 检查并终止占用 39997 端口的进程
PORT=39997
PID=$(lsof -ti:$PORT 2>/dev/null)
if [ -n "$PID" ]; then
    echo "⚠️  端口 $PORT 被占用，正在终止进程 $PID..."
    kill -9 $PID 2>/dev/null
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
    # 检查requirements.txt的时间戳，与已安装包比较来决定是否需要重新安装
    REQUIREMENTS_FILE="$PROJECT_ROOT/requirements.txt"
    PIP_CACHE_FILE=".pip_cache_timestamp"

    NEED_INSTALL=false

    if [ ! -f "$PIP_CACHE_FILE" ]; then
        # 时间戳文件不存在，需要安装
        NEED_INSTALL=true
        echo "📦 首次运行，正在安装依赖..."
    else
        # 比较requirements.txt和缓存时间戳
        if [ "$(uname)" = "Darwin" ]; then
            # macOS
            REQ_TS=$(stat -f%Sm -t%Y%m%d%H%M%S "$REQUIREMENTS_FILE" 2>/dev/null)
            CACHE_TS=$(cat "$PIP_CACHE_FILE" 2>/dev/null)
        else
            # Linux
            REQ_TS=$(stat -c%Y "$REQUIREMENTS_FILE" 2>/dev/null)
            CACHE_TS=$(cat "$PIP_CACHE_FILE" 2>/dev/null)
        fi

        if [ -n "$REQ_TS" ] && [ -n "$CACHE_TS" ]; then
            if [ "$REQ_TS" -gt "$CACHE_TS" ]; then
                NEED_INSTALL=true
                echo "📦 requirements.txt有更新，正在重新安装依赖..."
            fi
        elif [ -z "$REQ_TS" ] || [ -z "$CACHE_TS" ]; then
            NEED_INSTALL=true
            echo "📦 检测到依赖变化，正在重新安装..."
        fi
    fi

    if [ "$NEED_INSTALL" = true ]; then
        pip install -r "$REQUIREMENTS_FILE" -q

        # 记录当前时间戳到文件
        if [ "$(uname)" = "Darwin" ]; then
            # macOS
            TIMESTAMP=$(stat -f%Sm -t%Y%m%d%H%M%S "$REQUIREMENTS_FILE" 2>/dev/null || date +%Y%m%d%H%M%S)
        else
            # Linux
            TIMESTAMP=$(stat -c%Y "$REQUIREMENTS_FILE" 2>/dev/null || date +%Y%m%d%H%M%S)
        fi
        echo $TIMESTAMP > "$PIP_CACHE_FILE"
    else
        echo "✅ 依赖已是最新，跳过安装步骤"
    fi
else
    echo "警告: 未找到 requirements.txt 文件"
fi

# 启动服务
echo "🚀 启动后端服务，监听端口 $PORT..."
python server.py