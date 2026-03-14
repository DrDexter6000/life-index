# Life Index 一键安装脚本 (Windows PowerShell)
# 目标用户: 零编程基础的用户
#
# 使用方法:
#   1. 以管理员身份打开 PowerShell
#   2. 运行: Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
#   3. 运行: irm https://raw.githubusercontent.com/DrDexter6000/life-index/main/install.ps1 | iex
#

$ErrorActionPreference = "Stop"

# 颜色定义
function Write-Info($message) {
    Write-Host "[INFO] $message" -ForegroundColor Cyan
}

function Write-Success($message) {
    Write-Host "[SUCCESS] $message" -ForegroundColor Green
}

function Write-Warning($message) {
    Write-Host "[WARNING] $message" -ForegroundColor Yellow
}

function Write-Error($message) {
    Write-Host "[ERROR] $message" -ForegroundColor Red
}

# 检查系统要求
function Check-Requirements {
    Write-Info "检查系统要求..."
    
    # 检查 Python 3.11+
    try {
        $pythonVersion = python --version 2>&1
        if ($pythonVersion -match "Python 3\.(\d+)\.(\d+)") {
            $minorVersion = [int]$matches[1]
            if ($minorVersion -lt 11) {
                Write-Error "Python 版本过低。Life Index 需要 Python 3.11 或更高版本。"
                Write-Info "请访问 https://python.org 下载并安装 Python 3.11+"
                exit 1
            }
        }
        Write-Info "检测到 Python 版本: $pythonVersion"
    }
    catch {
        Write-Error "未检测到 Python。Life Index 需要 Python 3.11 或更高版本。"
        Write-Info "请访问 https://python.org 下载并安装 Python 3.11+"
        Write-Info "安装时请务必勾选 'Add Python to PATH'"
        exit 1
    }
    
    # 检查 pip
    try {
        $pipVersion = pip --version 2>&1
        Write-Info "检测到 pip: $pipVersion"
    }
    catch {
        Write-Error "未检测到 pip。请重新安装 Python 并确保勾选 'Add Python to PATH'"
        exit 1
    }
    
    Write-Success "系统检查通过"
}

# 安装 Life Index
function Install-LifeIndex {
    Write-Info "正在安装 Life Index..."
    
    # 创建临时目录
    $tempDir = Join-Path $env:TEMP "life-index-install-$(Get-Random)"
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    Set-Location $tempDir
    
    # 下载最新版本
    Write-Info "下载 Life Index..."
    try {
        git clone --depth 1 https://github.com/DrDexter6000/life-index.git 2>&1 | Out-Null
    }
    catch {
        Write-Warning "无法通过 git 克隆，尝试下载 zip 包..."
        $zipUrl = "https://github.com/DrDexter6000/life-index/archive/refs/heads/main.zip"
        Invoke-WebRequest -Uri $zipUrl -OutFile "life-index.zip"
        Expand-Archive -Path "life-index.zip" -DestinationPath "."
        Rename-Item "life-index-main" "life-index"
    }
    
    Set-Location "life-index"
    
    # 安装依赖（使用非 editable 模式，确保删除临时目录后仍可运行）
    Write-Info "安装核心依赖（这可能需要几分钟）..."
    pip install -q . 2>&1 | Select-String -NotMatch "already satisfied" | Out-Null

    # 询问是否安装语义搜索
    Write-Info ""
    $installSemantic = Read-Host "是否安装语义搜索功能？（需要下载 ~2GB 模型，推荐） [Y/n]"
    if ($installSemantic -eq "" -or $installSemantic -match "^[Yy]$") {
        Write-Info "正在安装语义搜索依赖（这可能需要 5-10 分钟）..."
        pip install -q ".[semantic]" 2>&1 | Select-String -NotMatch "already satisfied" | Out-Null
        Write-Success "语义搜索功能已启用"
    }
    else {
        Write-Warning "跳过了语义搜索安装。稍后可通过 'pip install life-index[semantic]' 启用"
    }
    
    # 创建数据目录
    Write-Info "创建数据目录..."
    $userDataDir = Join-Path $env:USERPROFILE "Documents\Life-Index"
    @("Journals", "by-topic", "attachments", ".life-index") | ForEach-Object {
        New-Item -ItemType Directory -Path (Join-Path $userDataDir $_) -Force | Out-Null
    }
    
    # 创建示例配置文件
    $configFile = Join-Path $userDataDir ".life-index\config.yaml"
    if (-not (Test-Path $configFile)) {
        @"
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
"@ | Out-File -FilePath $configFile -Encoding UTF8
        Write-Success "创建默认配置文件: $configFile"
    }
    
    # 清理
    Set-Location $env:USERPROFILE
    Remove-Item -Recurse -Force $tempDir -ErrorAction SilentlyContinue
    
    Write-Success "Life Index 安装完成！"
}

# 验证安装
function Verify-Installation {
    Write-Info "验证安装..."
    
    # 测试核心功能
    try {
        python -m tools.write_journal --help | Out-Null
        python -m tools.search_journals --help | Out-Null
    }
    catch {
        Write-Error "安装验证失败"
        exit 1
    }
    
    Write-Success "所有核心功能验证通过"
}

# 打印使用说明
function Print-Usage {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Success "Life Index 安装成功！"
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Info "数据目录: $env:USERPROFILE\Documents\Life-Index\"
    Write-Info "配置文件: $env:USERPROFILE\Documents\Life-Index\.life-index\config.yaml"
    Write-Host ""
    Write-Host "使用示例:"
    Write-Host '  1. 记录日志:'
    Write-Host '     python -m tools.write_journal --data ''{"title":"测试","content":"今天开始了新的项目","date":"2026-03-14","topic":["work"]}'''
    Write-Host ""
    Write-Host '  2. 搜索日志:'
    Write-Host '     python -m tools.search_journals --query "项目"'
    Write-Host ""
    Write-Host '  3. 查看天气:'
    Write-Host '     python -m tools.query_weather --location "Beijing"'
    Write-Host ""
    Write-Host "详细文档: https://github.com/DrDexter6000/life-index/blob/main/docs/HANDBOOK.md"
    Write-Host ""
    Write-Warning "提示: 将以上命令添加到 Agent 的 Skill 配置中即可开始使用"
    Write-Host ""
}

# 主流程
function Main {
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  Life Index 安装程序" -ForegroundColor Cyan
    Write-Host "  版本: 0.1.0" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    
    Check-Requirements
    Install-LifeIndex
    Verify-Installation
    Print-Usage
}

# 运行主流程
Main
