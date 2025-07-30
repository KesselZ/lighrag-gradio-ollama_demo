#!/bin/bash

# LightRAG 初始化脚本
# 用于设置 Ollama 环境和下载必要的模型

set -e  # 遇到错误立即退出

echo "🚀 开始初始化 LightRAG 环境..."

# 检查 Ollama 是否已安装
if ! command -v ollama &> /dev/null; then
    echo "❌ 错误: Ollama 未安装"
    echo "请先安装 Ollama: https://ollama.ai/download"
    exit 1
fi

# 检查 Ollama 服务是否运行
if ! curl -s http://localhost:11434/api/tags &> /dev/null; then
    echo "❌ 错误: Ollama 服务未运行"
    echo "请启动 Ollama 服务: ollama serve"
    exit 1
fi

echo "✅ Ollama 环境检查通过"

# 创建 .env 文件（如果不存在）
if [ ! -f .env ]; then
    echo "📝 创建 .env 配置文件..."
    cat > .env << EOF
# LightRAG 配置文件
LLM_MODEL=qwen2.5:7b
LLM_BINDING_HOST=http://localhost:11434
EMBEDDING_MODEL=bge-m3:latest
EMBEDDING_BINDING_HOST=http://localhost:11434
EMBEDDING_DIM=1024
MAX_EMBED_TOKENS=8192
TIMEOUT=300
VERBOSE_DEBUG=false
LOG_DIR=.
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5
EOF
    echo "✅ .env 文件创建完成"
else
    echo "✅ .env 文件已存在"
fi

# 下载 LLM 模型
echo " 开始下载 LLM 模型: qwen2.5:7b"
if ollama list | grep -q "qwen2.5:7b"; then
    echo "✅ qwen2.5:7b 模型已存在"
else
    echo "正在下载 qwen2.5:7b 模型，这可能需要几分钟..."
    ollama pull qwen2.5:7b
    echo "✅ qwen2.5:7b 模型下载完成"
fi

# 下载嵌入模型
echo "📥 开始下载嵌入模型: bge-m3:latest"
if ollama list | grep -q "bge-m3:latest"; then
    echo "✅ bge-m3:latest 模型已存在"
else
    echo "正在下载 bge-m3:latest 模型，这可能需要几分钟..."
    ollama pull bge-m3:latest
    echo "✅ bge-m3:latest 模型下载完成"
fi

# 检查 Python 依赖
echo "🔍 检查 Python 依赖..."
python3 -c "
import sys
import subprocess

def check_package(package_name, import_name=None):
    if import_name is None:
        import_name = package_name.replace('-', '_')
    
    try:
        __import__(import_name)
        return True
    except ImportError:
        return False

required_packages = [
    ('lightrag', 'lightrag'),
    ('python-dotenv', 'dotenv'),
    ('python-docx', 'docx')
]

missing_packages = []

for package, import_name in required_packages:
    if not check_package(package, import_name):
        missing_packages.append(package)

if missing_packages:
    print(f'❌ 缺少以下 Python 包: {missing_packages}')
    print('请运行: pip install ' + ' '.join(missing_packages))
    sys.exit(1)
else:
    print('✅ 所有 Python 依赖检查通过')
"

# 创建必要的目录
echo "📁 创建必要的目录..."
mkdir -p dickens
mkdir -p logs

# 简化测试 - 只检查 Ollama 服务是否响应
echo "🔧 测试 Ollama 服务连接..."
if curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "✅ Ollama 服务连接正常"
else
    echo "❌ Ollama 服务连接失败"
    exit 1
fi

# 检查模型是否存在
echo "🔍 检查模型是否已下载..."
if ollama list | grep -q "qwen2.5:7b" && ollama list | grep -q "bge-m3:latest"; then
    echo "✅ 所有必需模型已下载"
else
    echo "❌ 缺少必需模型，请确保已下载 qwen2.5:7b 和 bge-m3:latest"
    exit 1
fi

echo ""
echo "🎉 LightRAG 环境初始化完成！"
echo ""
echo "📋 下一步操作："
echo "1. 确保您的文档文件路径正确"
echo "2. 运行: python3 main.py"
echo "3. 或者运行带聊天模式: python3 main.py --chat_mode"
echo ""
echo "💡 提示："
echo "- 如果遇到模型下载问题，请检查网络连接"
echo "- 如果遇到权限问题，请确保有足够的磁盘空间"
echo "- 首次运行可能需要较长时间来建立索引"
