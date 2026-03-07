# Life Index

> 个人日志管理系统 - 记录、检索、回顾生活点滴

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 简介

Life Index 是一个开源的个人日志管理系统，帮助用户：

- 📝 **记录日志** - 按主题分类记录日常生活、工作、学习
- 🔍 **智能检索** - 支持全文搜索、语义搜索、多维度过滤
- 📊 **生成摘要** - 自动生成月度/年度总结
- 🏷️ **灵活标签** - 支持主题、项目、标签多维分类

## 特性

- **7大主题分类**：work(工作)、learn(学习)、health(健康)、relation(关系)、think(思考)、create(创作)、life(生活)
- **全文搜索**：基于 SQLite FTS5 的高效全文检索
- **语义搜索**：基于向量嵌入的语义相似度搜索
- **自动摘要**：AI 驱动的月度/年度总结生成
- **天气集成**：自动获取日志地点的天气信息
- **附件管理**：支持图片、文档等附件关联

## 安装

### 通过 ClawHub 安装（推荐）

```bash
clawhub install life-index
```

### 手动安装

```bash
git clone https://github.com/yourusername/life-index.git
cd life-index
pip install -r requirements.txt
```

## 快速开始

### 记录日志

```bash
python tools/write_journal.py --data '{
  "title": "完成搜索功能优化",
  "content": "今天优化了 Life Index 的搜索功能...",
  "topic": "work",
  "project": "Life-Index",
  "tags": ["重构", "优化"]
}'
```

### 搜索日志

```bash
# 全文搜索
python tools/search_journals.py --query "重构"

# 按主题过滤
python tools/search_journals.py --topic work --project Life-Index

# 语义搜索
python tools/search_journals.py --query "学习笔记" --semantic
```

### 生成摘要

```bash
# 月度摘要
python tools/generate_abstract.py --month 2026-03

# 年度摘要
python tools/generate_abstract.py --year 2026
```

## 项目结构

```
life-index/
├── tools/              # 核心工具脚本
│   ├── write_journal.py       # 写入日志
│   ├── search_journals.py     # 搜索日志
│   ├── edit_journal.py        # 编辑日志
│   ├── generate_abstract.py   # 生成摘要
│   ├── query_weather.py       # 天气查询
│   └── lib/                   # 库文件
│       ├── config.py
│       ├── search_index.py
│       └── semantic_search.py
├── docs/               # 文档
│   ├── ARCHITECTURE.md
│   ├── SCHEDULE.md
│   └── TOPIC_SYSTEM.md
├── tests/              # 测试
├── SKILL.md            # Agent 技能定义
└── README.md           # 本文件
```

## 数据存储

用户数据存储在 `~/Documents/Life-Index/`：

```
~/Documents/Life-Index/
├── Journals/           # 日志文件
│   └── YYYY/MM/
├── by-topic/           # 主题索引
└── attachments/        # 附件
```

## 文档

- [架构设计](docs/ARCHITECTURE.md)
- [定时任务](docs/SCHEDULE.md)
- [分类体系](docs/TOPIC_SYSTEM.md)

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

[MIT](LICENSE)

---

Made with ❤️ by [Your Name]
