# Life Index E2E 测试套件

## 测试框架说明

本目录包含 Life Index 的端到端（E2E）可靠性测试用例，采用**自然语言描述 + Agent 自主执行**的轻量方案。

## 文件结构

```
tests/e2e/
├── README.md                    # 本文件
├── phase1-core-workflow.yaml    # Phase 1: 核心工作流覆盖
├── phase2-search-retrieval.yaml # Phase 2: 搜索检索覆盖
├── phase3-edge-cases.yaml       # Phase 3: 边界与异常
└── phase4-edit-abstract.yaml    # Phase 4: Edit & Abstract Workflow
```

## 当前接入状态

| Phase | 文件 | 状态 |
|------|------|------|
| Phase 1 | `phase1-core-workflow.yaml` | 已接入 runner，已通过 |
| Phase 2 | `phase2-search-retrieval.yaml` | 已接入 runner，已通过 |
| Phase 3 | `phase3-edge-cases.yaml` | 已接入 runner，已通过 |
| Phase 4 | `phase4-edit-abstract.yaml` | 已接入 runner，已通过 |

## 执行方式

### Agent 执行指令

当用户说"执行 E2E 测试"时，Agent 应按以下流程执行：

1. **读取测试文件**
   - 按顺序读取 `phase1-*.yaml`、`phase2-*.yaml`、`phase3-*.yaml`、`phase4-*.yaml`
   - 解析 `test_cases` 列表

2. **逐一执行测试用例**
   - 按 `priority` 和 `id` 顺序执行
   - 每个测试用例记录：
     - 开始时间
     - 各步骤耗时（parse, weather_query, write_journal 等）
     - 实际结果
     - 通过/失败状态
     - 结束时间

3. **生成测试报告**
   - 输出到 `tests/reports/e2e-report-{timestamp}.md`
   - 包含：
     - 测试摘要（总数、通过数、失败数）
     - 性能指标对比（实际 vs SLA）
     - 失败用例详情

4. **清理测试数据**（如 `cleanup_after_test: true`）
   - 删除测试生成的日志文件
   - 删除测试生成的附件
   - 保留索引文件（可选）

## 数据隔离（强制）

- E2E runner 必须使用隔离的临时 `LIFE_INDEX_DATA_DIR`，**不得**默认写入真实用户目录 `~/Documents/Life-Index/`
- 人工调试若需要模拟真实数据结构，也必须先复制到临时目录后再执行
- 任何 E2E / 调试过程产生的日志、附件、索引都必须在临时目录内创建并在结束后清理
- 若某次人工调试误写入真实用户目录，执行人必须：
  1. 记录被写入的文件
  2. 删除污染文件
  3. 执行 `life-index index --rebuild`

### 手工调试 / 隔离验收推荐流程

优先使用隔离沙盒工具，而不是直接拿真实用户目录做验收：

```bash
# 创建一个全新的隔离调试沙盒
python -m tools.dev.run_with_temp_data_dir

# 如果需要复制当前用户数据做“仿真验收”
python -m tools.dev.run_with_temp_data_dir --seed
```

`--seed` 表示：
- 先复制当前用户数据到临时目录
- 再基于副本做隔离调试 / 验收
- **不会回写真实用户目录**

工具会打印：
- 临时 `LIFE_INDEX_DATA_DIR`
- 如何在该目录执行 `life-index health` / `life-index index`
- 调试结束后的清理提醒

## 测试用例格式规范

```yaml
test_suite:
  name: "Phase X - 名称"
  version: "1.0"
  executor: "Agent"
  cleanup_after_test: true

test_cases:
  - id: "E2E-XX"           # 唯一标识
    name: "测试名称"        # 人类可读名称
    priority: "P1/P2"      # 优先级
    description: "描述"     # 详细说明
    input:                 # 输入数据
      user_prompt: "..."
      data: {...}
    expected:              # 期望结果
      success: true
      ...
    performance_sla:       # 性能指标
      step_name: "< Xms"
```

多步骤工作流可使用：

```yaml
test_cases:
  - id: "E2E-XX"
    name: "多步骤测试"
    steps:
      - step: 1
        name: "创建日志"
        action: "write_journal"
        data: {...}
        expected: {...}
      - step: 2
        name: "编辑日志"
        action: "edit_journal"
        use_last_created: true
        operations:
          - set_topic: "learn"
        expected: {...}
      - step: 3
        name: "执行搜索"
        action: "search"
        query_params: {...}
        expected: {...}
      - step: 4
        name: "生成摘要"
        action: "generate_abstract"
        period: "month"
        value: "2026-03"
        expected: {...}
```

## 性能指标说明

| 指标 | 说明 | 典型值 |
|------|------|--------|
| parse | 语义解析时间 | < 500ms |
| weather_query | 天气查询时间 | < 2s |
| write_journal | 日志写入时间 | < 1s |
| search_l1 | L1索引搜索 | < 10ms |
| search_l2 | L2元数据搜索 | < 50ms |
| search_l3 | L3全文搜索 | < 100ms |
| total | 端到端总时间 | < 5s |

## 报告模板

测试报告应包含以下部分：

```markdown
# E2E 测试报告

## 摘要
- 测试时间: {timestamp}
- 总用例数: {N}
- 通过: {N} ✅
- 失败: {N} ❌
- 平均耗时: {X}s

## Phase 1: 核心工作流
| 用例 | 名称 | 状态 | 总耗时 | 备注 |
|------|------|------|--------|------|
| E2E-01 | ... | ✅ | 1.2s | - |

## 性能对比
| 指标 | SLA | 实际平均 | 达标率 |
|------|-----|---------|--------|
| parse | <500ms | 320ms | 100% |

## 失败详情
...
```
