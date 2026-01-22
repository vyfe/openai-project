#!/bin/bash
# 服务器生产环境启动脚本
# 功能：一键启动前后端生产服务

set -e

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

echo "🚀 启动生产环境服务..."

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

# 检查参数
RESTART=false
if [[ "$1" == "--restart" ]]; then
    RESTART=true
    echo "🔄 重启模式：将终止现有服务并重新启动"
fi

# 检查后端端口占用并终止占用进程
if [ $RESTART = true ]; then
    echo "🔍 检查后端端口 $SERVER_PORT 占用情况..."
    PORT_PIDS=$(lsof -ti:$SERVER_PORT 2>/dev/null)
    if [ -n "$PORT_PIDS" ]; then
        echo "⚠️  端口 $SERVER_PORT 被占用，正在终止进程 $PORT_PIDS..."
        kill -9 $PORT_PIDS 2>/dev/null
        sleep 2
    fi

    # 检查并终止现有的uwsgi进程
    UWSGI_PIDS=$(pgrep -f "uwsgi" 2>/dev/null)
    if [ -n "$UWSGI_PIDS" ]; then
        echo "⚠️  终止现有的 uWSGI 进程 $UWSGI_PIDS..."
        kill -9 $UWSGI_PIDS 2>/dev/null
        sleep 2
    fi
fi

# 创建项目目录
mkdir -p "$PROJECT_ROOT"

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

    # 移动文件到正确位置
    mv * .. 2>/dev/null || true
    cd ..
    rm -rf dist_tmp
    # add requirements.txt
    echo "✅ 后端代码解压完成"
else
    echo "❌ 错误: 未找到后端压缩包 '$BACKEND_TAR'"
    exit 1
fi

cd "$PROJECT_ROOT"
# add requirements.txt
pip install -r requirements.txt
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
pgrep uwsgi | xargs kill
# 等待服务杀死
sleep 3
uwsgi --ini ./conf/uwsgi.ini &

# 等待服务启动
sleep 3

# 检查后端是否成功启动
if lsof -i :$SERVER_PORT >/dev/null 2>&1; then
    echo "✅ 后端服务已在端口 $SERVER_PORT 启动"
else
    echo "❌ 错误: 后端服务启动失败，请检查日志"
    exit 1
fi

# 检查Nginx配置目录并提示配置Nginx
# 通过baota控制，不需要。
# if [ -d "$NGINX_CONF_DIR" ]; then
#     echo "💡 提示: 如果还没有配置Nginx，请将 nginx.conf.tpl 复制到 $NGINX_CONF_DIR/"
#     echo "💡 Nginx配置模板位于: $PROJECT_ROOT/cyf/project/fe/nginx.conf.tpl"
#     echo ""
#     echo "📋 Nginx配置示例:"
#     echo "server {"
#     echo "    listen $FRONTEND_PORT;"
#     echo "    server_name _;"
#     echo ""
#     echo "    # 前端静态文件"
#     echo "    location / {"
#     echo "        root $PROJECT_ROOT/cyf/project/fe/dist;"
#     echo "        index index.html;"
#     echo "        try_files \$uri \$uri/ /index.html;  # SPA 路由支持"
#     echo "    }"
#     echo ""
#     echo "    # API 代理到后端"
#     echo "    location /api {"
#     echo "        proxy_pass http://127.0.0.1:$SERVER_PORT;"
#     echo "        proxy_set_header Host \$host;"
#     echo "        proxy_set_header X-Real-IP \$remote_addr;"
#     echo "        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;"
#     echo "        proxy_set_header X-Forwarded-Proto \$scheme;"
#     echo "    }"
#     echo "}"
# else
#     echo "⚠️  警告: 未找到Nginx配置目录 '$NGINX_CONF_DIR'"
#     echo "💡 提示: 如需使用Nginx提供前端服务，请安装Nginx并创建配置文件"
#     echo "💡 或者手动配置反向代理到前端静态文件目录"
# fi

# # 重载Nginx配置（如果Nginx服务正在运行）
# if pgrep nginx >/dev/null; then
#     echo "🔄 检测到Nginx正在运行，尝试重载配置..."
#     nginx -s reload || echo "⚠️  Nginx重载失败，请手动重载配置"
# fi

echo ""
echo "🎉 生产环境服务启动完成！"
echo ""
echo "📊 服务状态："
echo "- 后端 API: http://localhost:$SERVER_PORT"
echo "- 前端页面: http://localhost (通过Nginx访问)"
echo ""
echo "🔧 管理命令："
echo "- 查看 uWSGI 进程: pgrep uwsgi"
echo "- 终止 uWSGI 进程: pkill -f uwsgi"
echo "- 重启服务: $0 --restart"
echo ""
echo "📝 日志位置："
echo "- uWSGI 日志: 查看配置文件中的日志设置"
echo "- Nginx 日志: /var/log/nginx/"