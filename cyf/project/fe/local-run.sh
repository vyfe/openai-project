#!/bin/bash

# 前端本地启动脚本
# 使用方法: ./local-run.sh 或 bash local-run.sh

# 获取脚本所在目录，确保从任何位置运行都能正确切换到前端目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查并终止占用 3000 端口的进程
PORT=3000
PID=$(lsof -ti:$PORT 2>/dev/null)
if [ -n "$PID" ]; then
    echo "⚠️  端口 $PORT 被占用，正在终止进程 $PID..."
    kill -9 $PID 2>/dev/null
    sleep 1
fi

echo "🚀 启动前端开发服务器..."
echo "📁 工作目录: $SCRIPT_DIR"

# 检查package.json和package-lock.json的时间戳，与node_modules比较来决定是否需要安装
NEED_INSTALL=false
NODE_MODULES_TS_FILE=".node_modules_timestamp"

if [ ! -d "node_modules" ]; then
    # node_modules目录不存在，需要安装
    NEED_INSTALL=true
    echo "📦 首次运行，正在安装依赖..."
elif [ -f "package.json" ]; then
    # 检查package.json是否比记录的时间戳更新
    if [ "$(uname)" = "Darwin" ]; then
        # macOS
        PKG_JSON_TS=$(stat -f%Sm -t%Y%m%d%H%M%S package.json 2>/dev/null)
    else
        # Linux
        PKG_JSON_TS=$(stat -c%Y package.json 2>/dev/null)
    fi

    if [ -f "$NODE_MODULES_TS_FILE" ]; then
        NODE_MODULES_TS=$(cat "$NODE_MODULES_TS_FILE" 2>/dev/null)

        if [ -n "$PKG_JSON_TS" ] && [ -n "$NODE_MODULES_TS" ] && [ "$PKG_JSON_TS" -gt "$NODE_MODULES_TS" ]; then
            NEED_INSTALL=true
            echo "📦 package.json有更新，正在重新安装依赖..."
        elif [ -f "package-lock.json" ]; then
            # 同时检查package-lock.json
            if [ "$(uname)" = "Darwin" ]; then
                # macOS
                PKG_LOCK_TS=$(stat -f%Sm -t%Y%m%d%H%M%S package-lock.json 2>/dev/null)
            else
                # Linux
                PKG_LOCK_TS=$(stat -c%Y package-lock.json 2>/dev/null)
            fi

            if [ -n "$PKG_LOCK_TS" ] && [ -n "$NODE_MODULES_TS" ] && [ "$PKG_LOCK_TS" -gt "$NODE_MODULES_TS" ]; then
                NEED_INSTALL=true
                echo "📦 package-lock.json有更新，正在重新安装依赖..."
            fi
        fi
    else
        # 时间戳文件不存在，需要重新安装
        NEED_INSTALL=true
        echo "📦 检测到依赖变化，正在重新安装..."
    fi
else
    # 没有package.json文件，无法确定依赖，重新安装
    NEED_INSTALL=true
    echo "📦 未找到package.json，正在重新安装依赖..."
fi

if [ "$NEED_INSTALL" = true ]; then
    npm install

    # 记录当前时间戳到文件
    TIMESTAMP_FILE="package.json"
    if [ -f "package-lock.json" ]; then
        TIMESTAMP_FILE="package-lock.json"
    fi

    if [ "$(uname)" = "Darwin" ]; then
        # macOS
        TIMESTAMP=$(stat -f%Sm -t%Y%m%d%H%M%S "$TIMESTAMP_FILE" 2>/dev/null || date +%Y%m%d%H%M%S)
    else
        # Linux
        TIMESTAMP=$(stat -c%Y "$TIMESTAMP_FILE" 2>/dev/null || date +%Y%m%d%H%M%S)
    fi
    echo $TIMESTAMP > "$NODE_MODULES_TS_FILE"
else
    echo "✅ 依赖已是最新，跳过安装步骤"
fi

echo "✅ 启动 Vite 开发服务器 (http://localhost:3000)"
npm run dev