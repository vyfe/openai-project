#!/bin/bash
# 本地生产环境打包脚本
# 功能：打包前后端代码为生产环境可用的压缩包

set -e

echo "📦 开始打包生产环境代码..."

# 获取项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
cd "$PROJECT_ROOT"

# 检查是否有dist目录，如果没有则创建
mkdir -p cyf/project/server/dist
mkdir -p cyf/project/fe/dist

echo "⚙️  开始打包后端代码..."

# 打包后端
cd cyf/project/server
python3 server_pack.py

echo "✅ 后端打包完成"

echo "⚙️  开始构建前端代码..."

# 构建前端
cd ../fe

# 检查是否已安装npm依赖
if [ ! -d "node_modules" ]; then
    echo "📦 安装前端依赖..."
    npm install
fi

# 构建前端
npm run build

echo "✅ 前端构建完成"

# 打包前端构建结果
cd dist
tar -czvf ../dist/fe.tar.gz ./

echo "✅ 前端打包完成"

mkdir -p $PROJECT_ROOT/dist
cp $PROJECT_ROOT/cyf/project/fe/dist/fe.tar.gz $PROJECT_ROOT/dist/
cp $PROJECT_ROOT/cyf/project/server/dist/server.tar.gz $PROJECT_ROOT/dist/
echo "🎉 打包&移动完成！"

echo "生成的文件："
echo "- $PROJECT_ROOT/dist/server.tar.gz (后端)"
echo "- $PROJECT_ROOT/dist/fe.tar.gz (前端)"

echo ""
echo "💡 接下来步骤："
echo "1. 将这两个压缩包上传到服务器"
echo "2. 在服务器上运行 start-prod.sh 脚本部署服务"

