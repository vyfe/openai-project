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

echo "🚚 将start-prod.sh、start-prod-quant、requirements.txt复制到dist目录..."
cp requirements.txt "$DIST_DIR/"
cp start-prod.sh "$DIST_DIR/"
cp start-prod-quant "$DIST_DIR/"
echo "✅ start-prod.sh、start-prod-quant已复制到dist目录"

echo "🗜️  开始打包整个dist目录..."

# 创建完整的打包名称
FULL_PACKAGE_NAME="openai-full-prod.tar.gz"
TEMP_FULL_PACKAGE="$PROJECT_ROOT/$FULL_PACKAGE_NAME"
rm -f "$DIST_DIR/$FULL_PACKAGE_NAME" "$TEMP_FULL_PACKAGE"
# 打包整个dist目录中的所有内容。先输出到项目根目录，避免把正在生成的 tar 包自身打进去。
tar -czvf "$TEMP_FULL_PACKAGE" -C "$DIST_DIR" ./
mv "$TEMP_FULL_PACKAGE" "$DIST_DIR/$FULL_PACKAGE_NAME"

echo "✅ 完整打包完成: $DIST_DIR/$FULL_PACKAGE_NAME"

# 返回项目根目录
cd "$PROJECT_ROOT"

# 自动删除原始文件（无交互确认）
echo ""
echo "🗑️  删除原始文件..."
rm -f dist/server.tar.gz
rm -f dist/fe.tar.gz
rm -f dist/start-prod.sh
rm -f dist/start-prod-quant
rm -f dist/nginx.conf.tpl
rm -f dist/requirements.txt
echo "✅ 原始文件已删除"

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
echo "   5. 启动量化子系统：nohup ./start-prod-quant --all --restart > start-prod-quant.out 2>&1 &"
echo ""
echo "💡 注意：服务器上需要安装 uWSGI, Nginx 和 tar 命令"
