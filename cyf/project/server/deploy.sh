#!/bin/bash
# 后端生产环境部署脚本
# 使用方式: ./deploy.sh [tar.gz路径] [port]
# 默认参数: ~/server.tar.gz 39997

set -e

# 默认值
DEFAULT_TAR_PATH="$HOME/server.tar.gz"
DEFAULT_PORT=39997

# 获取参数或使用默认值
TAR_FILE="${1:-$DEFAULT_TAR_PATH}"
PORT="${2:-$DEFAULT_PORT}"

echo "🚀 启动后端部署流程..."
echo "📦 源文件: $TAR_FILE"
echo "🔌 端口: $PORT"

# 检查源压缩包是否存在
if [ ! -f "$TAR_FILE" ]; then
    echo "❌ 错误: 源压缩包不存在 '$TAR_FILE'"
    exit 1
fi

# 检查当前目录是否为正确的项目目录
if [ ! -f "./conf/uwsgi.ini" ]; then
    echo "📍 当前不在部署目录，准备复制和解压..."
    # 复制并解压压缩包
    cp "$TAR_FILE" ./
    TAR_FILENAME=$(basename "$TAR_FILE")
    tar xf "$TAR_FILENAME"
    echo "✅ 压缩包已解压"
else
    echo "✅ 当前目录已存在部署文件"
fi

# 终止现有的 uWSGI 进程
echo "🔍 检查现有的 uWSGI 进程..."
EXISTING_PIDS=$(pgrep -f "uwsgi")
if [ -n "$EXISTING_PIDS" ]; then
    echo "⚠️  发现现有 uWSGI 进程 $EXISTING_PIDS，正在终止..."
    kill -TERM $EXISTING_PIDS 2>/dev/null || true
    sleep 2
    # 强制终止仍未关闭的进程
    EXISTING_PIDS_FORCE=$(pgrep -f "uwsgi")
    if [ -n "$EXISTING_PIDS_FORCE" ]; then
        echo "⚠️  仍有 uWSGI 进程运行，强制终止..."
        kill -9 $EXISTING_PIDS_FORCE 2>/dev/null || true
    fi
    echo "✅ uWSGI 进程已终止"
else
    echo "✅ 未发现现有 uWSGI 进程"
fi

# 检查虚拟环境是否存在
if [ -f "myenv/bin/activate" ]; then
    echo "🔌 激活虚拟环境..."
    source myenv/bin/activate
elif [ -f "../myenv/bin/activate" ]; then
    echo "🔌 激活上级目录虚拟环境..."
    source ../myenv/bin/activate
else
    echo "⚠️  未找到虚拟环境 'myenv'，使用系统 Python"
fi

# 检查 uWSGI 配置文件是否存在
if [ ! -f "./conf/uwsgi.ini" ]; then
    echo "❌ 错误: 未找到 uWSGI 配置文件 './conf/uwsgi.ini'"
    exit 1
fi

echo "⚙️  启动 uWSGI 服务..."
# 启动 uWSGI 服务
uwsgi --ini ./conf/uwsgi.ini

echo "🎉 后端部署完成！"