#!/bin/bash
# 服务器生产环境启动脚本
# 功能：一键启动前后端生产服务，支持仅更新前端、后端或全部更新

# set -e

# 配置项（可根据实际情况调整）
SERVER_PORT=39997           # 后端端口
FRONTEND_PORT=80            # 前端端口 (Nginx)
BACKEND_TAR="server.tar.gz" # 后端压缩包名
FRONTEND_TAR="fe.tar.gz"    # 前端压缩包名
# NGINX_CONF_DIR="/etc/nginx/conf.d"  # Nginx 配置目录
PROJECT_ROOT="$HOME/openai-project"

# 检查是否是被嵌套调用（在打包环境内运行）
CURRENT_DIR=$(pwd)
# 标准环境中运行，使用预设路径
echo "🏠 使用标准项目路径: $PROJECT_ROOT"

# 默认选项：更新全部
UPDATE_FRONTEND=true
UPDATE_BACKEND=true

echo "🚀 启动生产环境服务..."

# 显示帮助信息
show_help() {
    echo "用法: $0 [选项]"
    echo "选项:"
    echo "  --frontend-only     仅更新前端"
    echo "  --backend-only      仅更新后端"
    echo "  --all               更新全部（默认）"
    echo "  --restart           重启模式：终止现有服务并重新启动"
    echo "  --help              显示此帮助信息"
    exit 0
}

# 解析命令行参数
RESTART=false
for arg in "$@"; do
    case $arg in
        --frontend-only)
            UPDATE_FRONTEND=true
            UPDATE_BACKEND=false
            shift
            ;;
        --backend-only)
            UPDATE_FRONTEND=false
            UPDATE_BACKEND=true
            shift
            ;;
        --all)
            UPDATE_FRONTEND=true
            UPDATE_BACKEND=true
            shift
            ;;
        --rest)
            RESTART=true
            shift
            ;;
        --help|-h)
            show_help
            ;;
        *)
            echo "未知参数: $arg"
            show_help
            ;;
    esac
done

# 检查命令是否存在
check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo "❌ 错误: 未找到命令 '$1'"
        exit 1
    fi
}

# 检查必需命令
check_command "tar"
check_command "uwsgi"
check_command "nginx"

if [ $RESTART = true ]; then
    echo "🔄 重启模式：将终止现有服务并重新启动"

    # 首先尝试优雅地停止现有的uwsgi进程
    echo "🔍 查找并停止现有的 uWSGI 进程..."
    UWSGI_PIDS=$(pgrep -f "uwsgi" 2>/dev/null)
    if [ -n "$UWSGI_PIDS" ]; then
        echo "⚠️  终止现有的 uWSGI 进程 $UWSGI_PIDS..."
        kill -9 $UWSGI_PIDS 2>/dev/null
        # 等待优雅停止
        sleep 5
        # 再次检查是否有残留进程，如果有则强制终止
        UWSGI_PIDS_LEFT=$(pgrep -f "uwsgi.*server\.py\|uwsgi.*--ini\|uwsgi.*uwsgi\.ini" 2>/dev/null)
        if [ -n "$UWSGI_PIDS_LEFT" ]; then
            echo "⚠️  发现残留进程 $UWSGI_PIDS_LEFT，强制终止..."
            kill -9 $UWSGI_PIDS_LEFT 2>/dev/null
        fi
    fi

    # 等待端口释放
    echo "⏳ 等待端口 $SERVER_PORT 释放..."
    timeout 30 bash -c "while lsof -i:$SERVER_PORT; do sleep 1; done" 2>/dev/null || true
fi

# 创建项目目录
mkdir -p "$PROJECT_ROOT"

# 根据选项决定是否更新后端
if [ $UPDATE_BACKEND = true ]; then
    # 解压后端代码
    if [ -f "$BACKEND_TAR" ]; then
        echo "📦 解压后端代码..."

        # 清理现有后端代码
        rm -rf "$PROJECT_ROOT/cyf/project/server/dist_tmp" 2>/dev/null || true
        mkdir -p "$PROJECT_ROOT/cyf/project/server"
        cd "$PROJECT_ROOT/cyf/project/server"

        # 创建临时目录解压
        mkdir -p dist_tmp
        cd dist_tmp
        tar -xzf "../../../../$BACKEND_TAR"

        # 强制复制文件到正确位置，确保配置文件被正确覆盖
        for item in *; do
            if [ -d "$item" ] && [ -d "../$item" ]; then
                # 如果是目录且目标目录已存在，则递归强制复制覆盖
                cp -r -f --remove-destination "$item"/. "../$item"/
            elif [ -f "$item" ] && [ -f "../$item" ]; then
                # 如果是文件且目标文件已存在，则强制覆盖
                cp -f --remove-destination "$item" "../$item"
            else
                # 如果是新文件或目录，则直接移动
                mv "$item" "../$item"
            fi
        done
        cd ..
        rm -rf dist_tmp
        # add requirements.txt
        echo "✅ 后端代码解压完成（配置文件已正确覆盖）"
    else
        echo "❌ 错误: 未找到后端压缩包 '$BACKEND_TAR'"
        exit 1
    fi

    cd "$PROJECT_ROOT"
    # add requirements.txt
    pip install -r requirements.txt

    # 启动后端服务 (uWSGI)
    echo "⚙️  启动后端服务 (uWSGI)..."
    cd "$PROJECT_ROOT/cyf/project/server"

    # 检查是否有uwsgi配置文件
    if [ ! -f "./conf/uwsgi.ini" ]; then
        echo "❌ 错误: 未找到 uWSGI 配置文件 './conf/uwsgi.ini'"
        exit 1
    fi

    # 启动uWSGI服务
    echo "🏃‍♂️ 正在启动 uWSGI 服务..."
        # 等待服务启动
    which uwsgi
    sleep 3
    # 已知问题：uwsgi路径，必须使用lighthouse下的uwsgi
    /home/lighthouse/.local/bin/uwsgi --ini ./conf/uwsgi.ini &

    # 检查后端是否成功启动
    if lsof -i :$SERVER_PORT >/dev/null 2>&1; then
        echo "✅ 后端服务已在端口 $SERVER_PORT 启动"
    else
        echo "❌ 错误: 后端服务启动失败，请检查日志"
        exit 1
    fi
else
    echo "⏭️  跳过后端更新"
fi

# 根据选项决定是否更新前端
if [ $UPDATE_FRONTEND = true ]; then
    cd "$PROJECT_ROOT"
    # 解压前端代码
    if [ -f "$FRONTEND_TAR" ]; then
        echo "📦 解压前端代码..."

        # 清理现有前端代码
        rm -rf "$PROJECT_ROOT/cyf/project/fe/dist" 2>/dev/null || true
        mkdir -p "$PROJECT_ROOT/cyf/project/fe"
        cd "$PROJECT_ROOT/cyf/project/fe"

        # 解压前端代码
        tar -xzf "../../../$FRONTEND_TAR"

        echo "✅ 前端代码解压完成"
    else
        echo "❌ 错误: 未找到前端压缩包 '$FRONTEND_TAR'"
        exit 1
    fi
else
    echo "⏭️  跳过前端更新"
fi

echo ""
echo "🎉 生产环境服务启动完成！"
echo ""
echo "📊 服务状态："
if [ $UPDATE_BACKEND = true ]; then
    echo "- 后端 API: http://localhost:$SERVER_PORT"
fi
if [ $UPDATE_FRONTEND = true ]; then
    echo "- 前端页面: http://localhost (通过Nginx访问)"
fi
echo ""
echo "🔧 管理命令："
echo "- 查看 uWSGI 进程: pgrep uwsgi"
echo "- 终止 uWSGI 进程: pkill -f uwsgi"
echo "- 重启服务: $0 --restart"
echo ""
echo "📝 日志位置："
echo "- uWSGI 日志: 查看配置文件中的日志设置"
echo "- Nginx 日志: /var/log/nginx/"