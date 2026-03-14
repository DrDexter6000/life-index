#!/bin/bash
#
# Life Index 一键安装脚本 (Linux/macOS)
# 目标用户: 零编程基础的用户
# 
# 使用方法:
#   curl -fsSL https://raw.githubusercontent.com/DrDexter6000/life-index/main/install.sh | bash
#

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查系统要求
check_requirements() {
    print_info "检查系统要求..."
    
    # 检查 Python 3.11+
    if ! command -v python3 &> /dev/null; then
        print_error "未检测到 Python 3。Life Index 需要 Python 3.11 或更高版本。"
        print_info "请访问 https://python.org 下载并安装 Python 3.11+"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    print_info "检测到 Python 版本: $PYTHON_VERSION"
    
    # 检查 pip
    if ! command -v pip3 &> /dev/null; then
        print_error "未检测到 pip。请安装 pip: python3 -m ensurepip"
        exit 1
    fi
    
    print_success "系统检查通过"
}

# 安装 Life Index
install_life_index() {
    print_info "正在安装 Life Index..."
    
    # 创建临时目录
    TEMP_DIR=$(mktemp -d)
    cd "$TEMP_DIR"
    
    # 下载最新版本
    print_info "下载 Life Index..."
    git clone --depth 1 https://github.com/DrDexter6000/life-index.git 2>/dev/null || {
        print_warning "无法通过 git 克隆，尝试下载 zip 包..."
        curl -L -o life-index.zip https://github.com/DrDexter6000/life-index/archive/refs/heads/main.zip
        unzip -q life-index.zip
        mv life-index-main life-index
    }
    
    cd life-index
    
    # 安装依赖（使用非 editable 模式，确保删除临时目录后仍可运行）
    print_info "安装核心依赖（这可能需要几分钟）..."
    pip3 install -q . 2>&1 | grep -v "already satisfied" || true
    
    # 询问是否安装语义搜索
    print_info ""
    read -p "是否安装语义搜索功能？（需要下载 ~2GB 模型，推荐） [Y/n]: " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
        print_info "正在安装语义搜索依赖（这可能需要 5-10 分钟）..."
        pip3 install -q ".[semantic]" 2>&1 | grep -v "already satisfied" || true
        print_success "语义搜索功能已启用"
    else
        print_warning "跳过了语义搜索安装。稍后可通过 'pip3 install life-index[semantic]' 启用"
    fi
    
    # 创建数据目录
    print_info "创建数据目录..."
    USER_DATA_DIR="$HOME/Documents/Life-Index"
    mkdir -p "$USER_DATA_DIR"/{Journals,by-topic,attachments,.life-index}
    
    # 创建示例配置文件
    CONFIG_FILE="$USER_DATA_DIR/.life-index/config.yaml"
    if [ ! -f "$CONFIG_FILE" ]; then
        cat > "$CONFIG_FILE" << 'EOF'
# Life Index 用户配置文件
# 详细文档: https://github.com/DrDexter6000/life-index/blob/main/docs/HANDBOOK.md

# 默认地点（用于天气查询）
default_location: "Beijing, China"

# 索引前缀设置（可改为英文）
index_prefixes:
  topic: "主题_"
  project: "项目_"
  tag: "标签_"

# 自动摘要设置
abstract:
  # Agent 生成摘要时的默认字数
  max_length: 100
EOF
        print_success "创建默认配置文件: $CONFIG_FILE"
    fi
    
    # 清理
    cd /
    rm -rf "$TEMP_DIR"
    
    print_success "Life Index 安装完成！"
}

# 验证安装
verify_installation() {
    print_info "验证安装..."
    
    # 测试核心功能
    if ! python3 -m tools.write_journal --help &> /dev/null; then
        print_error "安装验证失败"
        exit 1
    fi
    
    if ! python3 -m tools.search_journals --help &> /dev/null; then
        print_error "安装验证失败"
        exit 1
    fi
    
    print_success "所有核心功能验证通过"
}

# 打印使用说明
print_usage() {
    echo ""
    echo "========================================"
    print_success "Life Index 安装成功！"
    echo "========================================"
    echo ""
    print_info "数据目录: $HOME/Documents/Life-Index/"
    print_info "配置文件: $HOME/Documents/Life-Index/.life-index/config.yaml"
    echo ""
    echo "使用示例:"
    echo "  1. 记录日志:"
    echo "     python3 -m tools.write_journal --data '{\"title\":\"测试\",\"content\":\"今天开始了新的项目\",\"date\":\"2026-03-14\",\"topic\":[\"work\"]}'"
    echo ""
    echo "  2. 搜索日志:"
    echo "     python3 -m tools.search_journals --query \"项目\""
    echo ""
    echo "  3. 查看天气:"
    echo "     python3 -m tools.query_weather --location \"Beijing\""
    echo ""
    echo "详细文档: https://github.com/DrDexter6000/life-index/blob/main/docs/HANDBOOK.md"
    echo ""
    print_warning "提示: 将以上命令添加到 Agent 的 Skill 配置中即可开始使用"
    echo ""
}

# 主流程
main() {
    echo "========================================"
    echo "  Life Index 安装程序"
    echo "  版本: 0.1.0"
    echo "========================================"
    echo ""
    
    check_requirements
    install_life_index
    verify_installation
    print_usage
}

# 运行主流程
main
