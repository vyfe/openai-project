#!/bin/bash
# 完整生产环境打包脚本
# 功能：将start-prod.sh移入dist目录，然后将整个dist目录打包，并删除源文件

set -e

echo "📦 开始完整打包生产环境代码..."

# 获取项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
cd "$PROJECT_ROOT"

# 检查是否已经执行了基本打包
if [ ! -f "dist/server.tar.gz" ] || [ ! -f "dist/fe.tar.gz" ]; then
    echo "⚠️  未检测到基本打包文件，正在运行pack-prod.sh进行打包..."
    ./pack-prod.sh
fi

echo "📁 检查dist目录..."
DIST_DIR="$PROJECT_ROOT/dist"
if [ ! -d "$DIST_DIR" ]; then
    echo "❌ 错误: 未找到 dist 目录"
    exit 1
fi

echo "🚚 将start-prod.sh、requirements.txt复制到dist目录..."
cp requirements.txt "$DIST_DIR/"
cp start-prod.sh "$DIST_DIR/"
echo "✅ start-prod.sh已复制到dist目录"

echo "🗜️  开始打包整个dist目录..."
cd "$DIST_DIR"

# 创建完整的打包名称
FULL_PACKAGE_NAME="openai-full-prod.tar.gz"
rm -f "$FULL_PACKAGE_NAME"
# 打包整个dist目录中的所有内容，排除tar文件本身
tar -czvf "$FULL_PACKAGE_NAME" ./

echo "✅ 完整打包完成: $DIST_DIR/$FULL_PACKAGE_NAME"

# 返回项目根目录
cd "$PROJECT_ROOT"

# 可选：询问用户是否删除源文件
echo ""
read -p "⚠️  是否删除原始文件？(输入 'yes' 确认删除): " DELETE_CONFIRMATION
if [ "$DELETE_CONFIRMATION" = "yes" ]; then
    echo "🗑️  删除原始文件..."
    rm -f dist/server.tar.gz
    rm -f dist/fe.tar.gz
    rm -f dist/start-prod.sh
    rm -f dist/nginx.conf.tpl
    rm -f dist/requirements.txt
    echo "✅ 原始文件已删除"
else
    echo "ℹ️  已跳过删除原始文件步骤"
fi

echo ""
echo "🎉 完整打包完成！"
echo ""
echo "📦 生成的完整包："
echo "   $PROJECT_ROOT/dist/$FULL_PACKAGE_NAME"
echo ""
echo "📤 部署说明："
echo "   1. 将 $FULL_PACKAGE_NAME 上传到服务器"
echo "   2. 在服务器上解压：tar -xzf $FULL_PACKAGE_NAME"
echo "   3. 进入解压后的目录：cd dist"
echo "   4. 运行部署脚本：./start-prod.sh"
echo ""
echo "💡 注意：服务器上需要安装 uWSGI, Nginx 和 tar 命令"