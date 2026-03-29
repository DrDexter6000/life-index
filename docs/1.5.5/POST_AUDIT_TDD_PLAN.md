# Life Index v1.5.5 审后修复 TDD 执行计划

> **基于**: 本次审计报告（v1.5.5 全面质量审计，含 Oracle + 3×Explore 交叉验证）
> **创建日期**: 2026-03-30
> **执行模式**: 由独立 Agent/LLM session 按 Phase → Batch → Task 顺序逐一执行
> **TDD 循环**: 每个 Task 严格遵循 Red → Green → Refactor
> **验收权威**: 以本文档中每个 Task 的「验收标准」为最终裁判；不满足则不得标记完成

---

## 执行须知（给执行 Agent 的指令）

### 开始前必读

1. **先读本文档**：完整阅读本文档全文，理解每个 Phase/Batch/Task 的上下文和依赖关系
2. **先读项目规范**：`AGENTS.md`（CLI-as-SSOT 原则、Web 层约束、测试防污染规则）
3. **先读共享库指南**：`tools/lib/AGENTS.md`（`lib/` 模块约定）
4. **确认分支**：在 `1.5.5` 分支上工作（`git checkout 1.5.5`），或按指示创建新分支
5. **确认工作树干净**：`git status` 显示 `nothing to commit, working tree clean`

### TDD 循环（每个 Task 必须遵循）

```
1. RED:      写一个会失败的测试（验证目标行为不存在或当前行为错误）
             ⚠️ 必须先运行测试确认它确实 FAIL（不是 ERROR，是预期的 FAIL）
2. GREEN:    写最少代码使测试通过
             ⚠️ 只写刚好让测试通过的代码，不多写
3. REFACTOR: 清理代码但不改变行为，确保测试仍通过
4. VERIFY:   运行完整测试套件确认无回归
             ⚠️ 必须运行下方「验证命令」中的全量测试
```

### 验证命令

```bash
# ===== 每个 Task 完成后必跑 =====

# 单元测试（必跑）
python -m pytest tests/unit/ -v --timeout=60

# Contract 测试（必跑）
python -m pytest tests/contract/ -v --timeout=60

# 全量测试（必跑）
python -m pytest tests/ -v --timeout=300 --benchmark-disable

# 类型检查（必跑）
mypy tools/ --ignore-missing-imports

# 代码风格检查（必跑）
flake8 tools/ web/ --count --max-complexity=40 --max-line-length=100

# ===== 快速验证单个文件（可选，调试用） =====
# python -m pytest tests/unit/test_xxx.py -v -x
```

### 关键约束（违反任一项则 Task 不合格）

1. **不得引入新的 `# type: ignore` 或 `noqa` 注释**（除非是 `__init__.py` 的 re-export `noqa: F401`）
2. **不得引入新的 `print()` 调用**（必须使用 `logger`）
3. **不得引入 `from unittest.mock import` 到非测试文件**
4. **不得使用 `as any`、`@ts-ignore` 等类型压制**
5. **不得修改现有公开 API 的返回值结构**（只能添加字段，不能删除或改变已有字段的类型）
6. **不得跳过验证命令**——每个 Task 完成后必须跑全量测试并确认 0 failures

### 执行记录格式

每完成一个 Task，在该 Task 的 `执行记录` 区块填写：

```
执行记录:
- 执行时间: YYYY-MM-DD HH:MM
- 执行 Agent/Session: [session ID 或标识]
- RED 测试文件: [新建/修改的测试文件路径]
- RED 确认失败: ✅ 测试确实 FAIL / ❌ 未验证
- GREEN 实现: [修改的源文件路径和关键变更摘要]
- REFACTOR: [清理内容摘要，或 "无需重构"]
- 全量测试: ✅ X passed, Y skipped, 0 failed / ❌ [失败详情]
- mypy: ✅ N errors (same or fewer than before) / ❌ [新增错误]
- flake8: ✅ 0 errors / ❌ [错误详情]
- 备注: [遇到的问题、偏离计划的地方、后续需注意的点]
```

---

## 总览：Phase → Batch → Task

```
Phase 1 (P0): 发布卫生 — 立即修复的基础项
  ├── Task 1-1: pyproject.toml 版本号 bump
  ├── Task 1-2: CHANGELOG 补录 FIX-10
  └── Task 1-3: print() → logger 替换

Phase 2 (P1): 生产-测试边界修复 — 核心代码质量问题
  ├── Task 2-1: 移除 semantic_pipeline.py 中的 Mock import
  └── Task 2-2: except Exception 添加 logging

Phase 3 (P2): DRY 重复消除
  └── Task 3-1: _load_yaml_config / _deep_merge 提取到 yaml_utils.py

Phase 4 (P3): 类型注解统一与补全
  ├── Task 4-1: keyword_pipeline.py 旧式 typing → 内建泛型
  └── Task 4-2: schema.py 补全返回类型注解

Phase 5 (P4): CI 加固 — 让 CI 真正有效
  ├── Task 5-1: 添加 coverage gate 到 CI
  └── Task 5-2: bandit 配置文件化 + B311 评估

Phase 6 (P5): 测试完善
  ├── Task 6-1: field_sources 专项 unit test
  └── Task 6-2: TDD 计划执行记录文档修正
```

### 依赖关系

```
Phase 1 ──→ Phase 2（先修发布卫生，再改代码逻辑）
Phase 2 ──→ Phase 3（先修反模式，再合并重复代码）
Phase 3 ──→ Phase 4（重复消除后再做类型修正，避免改两遍）
Phase 4 ──→ Phase 5（代码稳定后加固 CI）
Phase 5 ──→ Phase 6（CI 就位后补测试，确保新测试也跑在 CI 里）
```

### 当前基线（执行前确认）

```
全量测试:   1500+ passed, 8 skipped, 0 failed
Benchmark:  16 passed
flake8:     0 errors
mypy:       13 errors（本计划不承诺降低此数字，但不得增加）
```

---

## Phase 1: 发布卫生 — P0

> **目标**: 修复审计发现的 3 个零风险基础问题。这些修改不涉及任何逻辑变更，只是修正遗漏。
>
> **估时**: 每个 Task < 15 分钟

### Task 1-1: pyproject.toml 版本号 bump

**问题**: `pyproject.toml` line 11 仍为 `version = "1.5.0"`，与分支名 `1.5.5` 不一致。

**目标文件**: `pyproject.toml`

**修改内容**:
- 将 `version = "1.5.0"` 改为 `version = "1.5.5"`

**RED**: 新建 `tests/unit/test_version_bump.py`（或扩展已有的 `tests/unit/test_cli_version.py`）
```python
def test_pyproject_version_is_1_5_5():
    """pyproject.toml 版本必须为 1.5.5"""
    import tomllib  # Python 3.11+
    from pathlib import Path

    pyproject = Path(__file__).parent.parent.parent / "pyproject.toml"
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
    assert data["project"]["version"] == "1.5.5"
```

**GREEN**: 修改 `pyproject.toml` line 11: `version = "1.5.0"` → `version = "1.5.5"`

**验收标准**:
- [ ] `grep 'version = "1.5.5"' pyproject.toml` 有输出
- [ ] 新测试通过
- [ ] 全量测试 0 failures

**执行记录**:
```
（待填写）
```

---

### Task 1-2: CHANGELOG 补录 FIX-10

**问题**: `docs/CHANGELOG.md` 的 `[1.5.5]` 部分遗漏了 FIX-10（P0 Web SSOT 修复），这是 v1.5.5 最高优先级的工作，反而没有记录。

**目标文件**: `docs/CHANGELOG.md`

**修改内容**: 在 `## [1.5.5] - 2026-03-29` 下的 `### 代码重构 (Refactoring)` 部分，**在最前面**（因为 FIX-10 是 P0）添加以下内容：

```markdown
#### Web SSOT 修复 + Metadata Enrichment [FIX-10]

- **FIX-10**: Web 层业务逻辑清除
  - 新建 `tools/write_journal/prepare.py` (376 lines) — CLI 层 metadata enrichment pipeline
  - 新建 `tools/lib/llm_extract.py` — LLM 元数据提取
  - 新建 `tools/lib/text_normalize.py` — 文本规范化工具
  - `web/services/write.py` 341→186 行，移除所有业务逻辑（LLM 提取、天气查询、数据转换）
  - 添加 `field_sources` 追踪机制（记录每个字段由用户/AI/规则填入）
  - `tools/write_journal/__main__.py` 添加 `enrich` CLI 子命令
```

**这个 Task 不需要 RED 测试**（纯文档变更），但需要验证：
- [ ] `docs/CHANGELOG.md` 中 `[1.5.5]` 部分包含 `FIX-10` 字样
- [ ] FIX-10 位于其他 FIX 项之前（因为它是 P0）
- [ ] 全量测试仍然 0 failures（确认没有误改代码文件）

**执行记录**:
```
（待填写）
```

---

### Task 1-3: print() → logger 替换

**问题**: `tools/lib/fts_search.py:190` 和 `tools/lib/fts_update.py:76` 在错误处理中使用 `print()` 而非 `logger`，导致线上不可观测。

**目标文件**:
- `tools/lib/fts_search.py` — line 190
- `tools/lib/fts_update.py` — line 76

**当前代码（fts_search.py:190）**:
```python
print(f"FTS search error: {e}")
```

**当前代码（fts_update.py:76）**:
```python
print(f"Warning: Failed to parse {file_path}: {e}")
```

**RED**: 新建 `tests/unit/test_fts_logging.py`
```python
import logging

def test_fts_search_uses_logger_not_print(caplog, tmp_path):
    """fts_search 的错误应通过 logger 记录，而非 print"""
    # 构造一个会触发异常的场景（如传入损坏的 DB 路径）
    from tools.lib.fts_search import search_fts
    with caplog.at_level(logging.ERROR):
        # 用一个不存在或损坏的 DB 路径触发错误
        results = search_fts(
            query="test",
            fts_db_path=tmp_path / "nonexistent.db"
        )
    # 验证 logger 记录了错误（而非 print）
    assert any("FTS" in r.message or "error" in r.message.lower() for r in caplog.records)

def test_fts_update_uses_logger_not_print(caplog, tmp_path):
    """fts_update 的 parse 警告应通过 logger 记录，而非 print"""
    # 构造一个会触发 parse 失败的场景
    bad_file = tmp_path / "bad.md"
    bad_file.write_text("not a valid journal file", encoding="utf-8")

    from tools.lib.fts_update import parse_journal
    with caplog.at_level(logging.WARNING):
        result = parse_journal(bad_file)
    # parse_journal 应该通过 logger 报告问题
    # 注意: 如果 parse_journal 不直接含 print，测试可能需要调整
```

⚠️ **注意**: 上面的 RED 测试是示意。你需要先阅读 `fts_search.py` 的 `search_fts()` 函数签名和 `fts_update.py` 的 `parse_journal()` 函数签名，确认正确的参数和触发异常的方式。如果函数签名与示意代码不同，请调整测试代码。

**GREEN**:
1. 在 `fts_search.py` 顶部确认有 logger 实例（查找 `logger = ` 或 `get_logger(`）。如果没有，添加：
   ```python
   import logging
   logger = logging.getLogger(__name__)
   ```
2. 将 `fts_search.py:190` 的 `print(f"FTS search error: {e}")` 替换为 `logger.error("FTS search error: %s", e)`
3. 在 `fts_update.py` 顶部确认有 logger 实例。如果没有，添加。
4. 将 `fts_update.py:76` 的 `print(f"Warning: Failed to parse {file_path}: {e}")` 替换为 `logger.warning("Failed to parse %s: %s", file_path, e)`

**验收标准**:
- [ ] `grep -n "print(" tools/lib/fts_search.py tools/lib/fts_update.py` 返回空（这两个文件中不再有 `print()` 调用）
- [ ] 新测试通过
- [ ] 全量测试 0 failures
- [ ] flake8 0 errors

**执行记录**:
```
（待填写）
```

---

### Phase 1 完成验收

```bash
python -m pytest tests/ -v --timeout=300 --benchmark-disable
mypy tools/ --ignore-missing-imports
flake8 tools/ web/ --count --max-complexity=40 --max-line-length=100

# 关键检查：
# 1. pyproject.toml version == "1.5.5"
# 2. CHANGELOG.md 包含 FIX-10
# 3. fts_search.py 和 fts_update.py 中无 print() 调用
# 4. 零测试失败
# 5. mypy errors 不多于 13 个
```

---

## Phase 2: 生产-测试边界修复 — P1

> **目标**: 修复两个影响代码健康度的反模式：生产代码依赖测试基础设施（Mock import）和错误被吞（except Exception 无 logging）。
>
> **风险提示**: Phase 2 涉及搜索管道的运行时行为判断逻辑变更，修改后必须严格验证搜索功能正常。

### Task 2-1: 移除 semantic_pipeline.py 中的 Mock import

**问题**: `tools/search_journals/semantic_pipeline.py:12` 有 `from unittest.mock import Mock`，生产代码在 line ~87 使用 `isinstance(search_semantic, Mock)` 来判断语义搜索是否可用。这是一个**严重的反模式**——生产代码永远不应依赖测试基础设施。

**目标文件**: `tools/search_journals/semantic_pipeline.py`

**当前问题代码（审查确认）**:
```python
# line 12
from unittest.mock import Mock

# line ~87（在函数内部）
if isinstance(search_semantic, Mock):
    # 判断为不可用
```

**修复方案**: 改为使用 `callable()` 检查 + 函数行为检测，而非检查是否为 Mock 实例。

具体策略：
1. 移除 `from unittest.mock import Mock` import
2. 将 `isinstance(search_semantic, Mock)` 替换为以下逻辑之一（按优先级选择）：
   - **方案 A（推荐）**: 检查 `get_semantic_runtime_status()` 的返回值来判断可用性。如果该函数已返回 `{"available": False}` 表示不可用，直接用它的返回值。
   - **方案 B**: 检查 `callable(search_semantic)` 加上 `hasattr(search_semantic, '__module__')` 来确认不是 mock
   - **方案 C**: 在模块加载时设一个 `_SEMANTIC_AVAILABLE: bool` 标志

**RED**: 新建 `tests/unit/test_semantic_pipeline_no_mock_import.py`
```python
import ast
from pathlib import Path

def test_semantic_pipeline_does_not_import_mock():
    """生产代码不得 import unittest.mock"""
    source_file = Path("tools/search_journals/semantic_pipeline.py")
    source = source_file.read_text(encoding="utf-8")
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module != "unittest.mock", (
                f"生产代码 semantic_pipeline.py line {node.lineno} "
                f"不得 import unittest.mock"
            )
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "unittest.mock" not in alias.name, (
                    f"生产代码 semantic_pipeline.py line {node.lineno} "
                    f"不得 import unittest.mock"
                )

def test_semantic_pipeline_degrades_without_mock_check():
    """语义管道在模型不可用时仍应正确降级"""
    from unittest.mock import patch, MagicMock
    from tools.search_journals.semantic_pipeline import run_semantic_pipeline

    # Mock search_semantic 为一个普通函数（不是 Mock 类型）
    # 但让 get_semantic_runtime_status 返回 unavailable
    with patch(
        "tools.search_journals.semantic_pipeline.get_semantic_runtime_status",
        return_value={"available": False, "reason": "Model not loaded"},
    ):
        results, perf, available, note = run_semantic_pipeline(query="test")
        assert available is False
        assert isinstance(results, list)
```

⚠️ **注意**: 上面的 RED 测试中 `run_semantic_pipeline` 的返回值签名是基于审计中观察到的 `(results, perf, available, note)` 四元组。执行前请先阅读 `semantic_pipeline.py` 确认实际签名，如有不同请调整。

**GREEN**:
1. 阅读 `semantic_pipeline.py` 全文（110 行），理解 `get_semantic_runtime_status()` 的返回值结构
2. 移除 line 12 的 `from unittest.mock import Mock`
3. 找到所有 `isinstance(..., Mock)` 调用，替换为 `get_semantic_runtime_status()` 的 `available` 字段检查
4. 确保降级路径（返回空列表 + 原因说明）不变

**验收标准**:
- [ ] `grep -n "unittest.mock" tools/search_journals/semantic_pipeline.py` 返回空
- [ ] `grep -rn "isinstance.*Mock" tools/` 返回空（整个 tools/ 目录中不应有此模式）
- [ ] 新 AST 测试通过
- [ ] 降级测试通过
- [ ] 全量测试 0 failures（尤其关注 `tests/unit/test_search_journals_core.py` 和 `tests/integration/test_search_pipeline.py`）
- [ ] 全量搜索测试通过：`python -m pytest tests/ -k "search" -v --timeout=300`

**执行记录**:
```
（待填写）
```

---

### Task 2-2: except Exception 添加 logging

**问题**: 两处 `except Exception` 捕获异常后不通过 `logger` 记录，错误信息只存在于 JSON 输出或内部 dict 中，对于后续排障无帮助。

**目标文件**:
- `tools/write_journal/__main__.py` — line 92
- `tools/write_journal/prepare.py` — line 270

**修改内容**:

对于 `__main__.py:92`（先阅读上下文确认当前代码）:
```python
# 当前（预期）:
except Exception as e:
    print(json.dumps({"success": False, "error": str(e)}, ...))

# 修改为:
except Exception as e:
    logger.exception("write_journal failed: %s", e)
    print(json.dumps({"success": False, "error": str(e)}, ...))
```

对于 `prepare.py:270`（先阅读上下文确认当前代码）:
```python
# 当前（预期）:
except Exception as exc:
    llm_status["error"] = str(exc)

# 修改为:
except Exception as exc:
    logger.warning("LLM enrichment failed, continuing without: %s", exc)
    llm_status["error"] = str(exc)
```

⚠️ **重要**: 执行前必须阅读这两个文件的对应行号附近 ±10 行的上下文，确认：
1. 当前代码确实如上所述
2. 该文件已有 `logger` 实例（如果没有，需要先添加）
3. `logger.exception()` 用于 `__main__.py`（因为这是顶层错误，需要 traceback）
4. `logger.warning()` 用于 `prepare.py`（因为 LLM enrichment 失败可以容忍，不是致命错误）

**RED**: 新建 `tests/unit/test_exception_logging.py`
```python
import logging

def test_write_journal_main_logs_on_exception(caplog):
    """write_journal __main__ 的异常必须通过 logger 记录"""
    # 这个测试需要 mock write_journal 的核心函数使其抛出异常
    # 然后验证 caplog 中有相应的日志记录
    # 具体实现取决于 __main__.py 的结构

def test_prepare_logs_on_llm_failure(caplog):
    """prepare.py 的 LLM enrichment 失败必须通过 logger 记录"""
    # 需要 mock LLM 调用使其抛出异常
    # 然后验证 caplog 中有 warning 级别的日志
```

⚠️ **注意**: 上面的 RED 测试是骨架。你需要先阅读 `__main__.py` 和 `prepare.py` 的相关函数，理解它们的调用链和可 mock 的注入点，然后完善测试。

**验收标准**:
- [ ] `__main__.py:92` 附近有 `logger.exception()` 或 `logger.error()` 调用
- [ ] `prepare.py:270` 附近有 `logger.warning()` 调用
- [ ] 新测试通过
- [ ] 全量测试 0 failures

**执行记录**:
```
（待填写）
```

---

### Phase 2 完成验收

```bash
python -m pytest tests/ -v --timeout=300 --benchmark-disable
mypy tools/ --ignore-missing-imports
flake8 tools/ web/ --count --max-complexity=40 --max-line-length=100

# 关键检查：
# 1. tools/ 目录中无 "from unittest.mock" import（除了 conftest/test 文件）
# 2. tools/ 目录中无 "isinstance.*Mock" 模式
# 3. 全量搜索测试通过：python -m pytest tests/ -k "search" -v
# 4. mypy errors 不多于 13 个
```

---

## Phase 3: DRY 重复消除 — P2

> **目标**: 消除 `_load_yaml_config()` 和 `_deep_merge()` 在 `paths.py` 和 `config.py` 中的重复定义。
>
> **风险**: 这两个函数被多个路径使用，提取时必须保证所有调用方不受影响。

### Task 3-1: 提取 _load_yaml_config / _deep_merge 到 yaml_utils.py

**问题**: `_load_yaml_config()` 和 `_deep_merge()` 在两个文件中各有一份独立实现：
- `tools/lib/paths.py`: lines 144, 156（被 line 212, 324-325 调用）
- `tools/lib/config.py`: lines 66, 102（被 line 121, 124, 171, 201, 215 调用）

两份实现逻辑相同，违反 DRY 原则。

**目标文件**:
- 新建: `tools/lib/yaml_utils.py`
- 修改: `tools/lib/paths.py`
- 修改: `tools/lib/config.py`

**RED**: 新建 `tests/unit/test_yaml_utils.py`
```python
from pathlib import Path
import pytest

def test_load_yaml_config_returns_dict(tmp_path):
    """有效的 YAML 文件应返回 dict"""
    from tools.lib.yaml_utils import load_yaml_config

    config_file = tmp_path / "test.yaml"
    config_file.write_text("key: value\nnested:\n  inner: 42\n", encoding="utf-8")
    result = load_yaml_config(config_file)
    assert result == {"key": "value", "nested": {"inner": 42}}

def test_load_yaml_config_missing_file(tmp_path):
    """不存在的文件应返回空 dict，不抛异常"""
    from tools.lib.yaml_utils import load_yaml_config

    result = load_yaml_config(tmp_path / "nonexistent.yaml")
    assert result == {}

def test_load_yaml_config_invalid_yaml(tmp_path):
    """无效 YAML 应返回空 dict，不抛异常"""
    from tools.lib.yaml_utils import load_yaml_config

    config_file = tmp_path / "bad.yaml"
    config_file.write_text("{{{{invalid yaml", encoding="utf-8")
    result = load_yaml_config(config_file)
    assert result == {}

def test_deep_merge_basic():
    """深度合并：override 覆盖 base"""
    from tools.lib.yaml_utils import deep_merge

    base = {"a": 1, "b": {"c": 2, "d": 3}}
    override = {"b": {"c": 99, "e": 5}}
    result = deep_merge(base, override)
    assert result == {"a": 1, "b": {"c": 99, "d": 3, "e": 5}}

def test_deep_merge_does_not_mutate_base():
    """合并不应修改原始 dict"""
    from tools.lib.yaml_utils import deep_merge

    base = {"a": {"b": 1}}
    override = {"a": {"c": 2}}
    result = deep_merge(base, override)
    assert base == {"a": {"b": 1}}  # 原始未被修改
    assert result == {"a": {"b": 1, "c": 2}}

def test_deep_merge_empty_override():
    """空 override 应返回 base 的副本"""
    from tools.lib.yaml_utils import deep_merge

    base = {"a": 1}
    result = deep_merge(base, {})
    assert result == {"a": 1}
```

**GREEN**:
1. 新建 `tools/lib/yaml_utils.py`:
   ```python
   """
   YAML 配置文件加载与深度合并工具。

   从 paths.py 和 config.py 提取的公共函数，消除重复代码。
   """
   import logging
   from pathlib import Path
   from typing import Any, Dict

   logger = logging.getLogger(__name__)

   def load_yaml_config(config_path: Path) -> Dict[str, Any]:
       """加载 YAML 配置文件，文件不存在或解析失败时返回空 dict。"""
       # 从 paths.py 的 _load_yaml_config 复制实现
       ...

   def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
       """深度合并两个 dict，override 优先。不修改输入参数。"""
       # 从 paths.py 的 _deep_merge 复制实现
       ...
   ```

2. 修改 `tools/lib/paths.py`:
   - 移除 `_load_yaml_config()` 和 `_deep_merge()` 的本地定义
   - 添加 `from .yaml_utils import load_yaml_config, deep_merge`
   - 将所有内部调用从 `_load_yaml_config(...)` 改为 `load_yaml_config(...)`
   - 将所有内部调用从 `_deep_merge(...)` 改为 `deep_merge(...)`
   - 更新 `__all__` 列表（移除 `_load_yaml_config` 和 `_deep_merge`）

3. 修改 `tools/lib/config.py`:
   - 同上操作

4. 可选：在 `tools/lib/__init__.py` 添加 re-export（如果外部有使用）

**验收标准**:
- [ ] `tools/lib/yaml_utils.py` 存在且 < 60 行
- [ ] `grep -n "_load_yaml_config\|_deep_merge" tools/lib/paths.py` 返回空（本地定义已移除）
- [ ] `grep -n "_load_yaml_config\|_deep_merge" tools/lib/config.py` 返回空（本地定义已移除）
- [ ] `grep -n "from .yaml_utils import" tools/lib/paths.py tools/lib/config.py` 各有 1 行
- [ ] 新测试全部通过
- [ ] 全量测试 0 failures
- [ ] mypy errors 不多于 13 个

⚠️ **特别注意**: `paths.py` 的 `__all__` 中当前导出了 `_load_yaml_config` 和 `_deep_merge`（见 line 366-367）。移除后检查是否有外部代码 import 这两个私有函数。用以下命令检查：
```bash
grep -rn "_load_yaml_config\|_deep_merge" tools/ web/ tests/ --include="*.py" | grep -v "yaml_utils.py" | grep -v "__pycache__"
```
如果有外部引用，需要同步更新或在 `yaml_utils.py` 中设置公开名（不带下划线前缀）。

**执行记录**:
```
（待填写）
```

---

### Phase 3 完成验收

```bash
python -m pytest tests/ -v --timeout=300 --benchmark-disable
mypy tools/ --ignore-missing-imports
flake8 tools/ web/ --count --max-complexity=40 --max-line-length=100

# 关键检查：
# 1. yaml_utils.py 存在且被 paths.py 和 config.py import
# 2. paths.py 和 config.py 中不再有 _load_yaml_config / _deep_merge 定义
# 3. 全量测试 0 failures
```

---

## Phase 4: 类型注解统一与补全 — P3

> **目标**: 统一代码库中的类型注解风格，补全缺失的返回类型。
>
> **核心原则**: Python 3.11+ 项目应使用内建泛型 (`list`, `dict`, `tuple`) 而非 `typing` 模块的旧式泛型 (`List`, `Dict`, `Tuple`)。

### Task 4-1: keyword_pipeline.py 旧式 typing → 内建泛型

**问题**: `tools/search_journals/keyword_pipeline.py:11` 使用 `from typing import Any, Dict, List, Optional, Tuple`，与项目其他模块使用的内建泛型不一致。

**目标文件**: `tools/search_journals/keyword_pipeline.py`

**修改内容**:
1. 移除 `from typing import Dict, List, Optional, Tuple` 中的 `Dict`, `List`, `Optional`, `Tuple`
   - 如果 `Any` 仍被使用，保留 `from typing import Any`
   - 如果 `Optional` 被使用，替换为 `X | None` 语法
2. 在整个文件中替换：
   - `Dict[` → `dict[`
   - `List[` → `list[`
   - `Tuple[` → `tuple[`
   - `Optional[X]` → `X | None`

⚠️ **执行步骤**（逐步执行，每步后验证）:
1. 先读取整个文件，统计所有使用旧式泛型的位置
2. 逐一替换（用全局搜索替换，不要手动逐行改）
3. 更新 import 行
4. 运行 `python -c "import tools.search_journals.keyword_pipeline"` 确认语法正确
5. 运行全量测试

**RED**: 新建 `tests/unit/test_typing_modern.py`
```python
import ast
from pathlib import Path

PRODUCTION_FILES = [
    "tools/search_journals/keyword_pipeline.py",
]

OLD_TYPING_NAMES = {"Dict", "List", "Tuple", "Optional", "Set", "FrozenSet"}

def test_no_old_style_typing_imports():
    """生产代码不应 import typing 模块的旧式泛型（Python 3.11+ 用内建泛型）"""
    for filepath in PRODUCTION_FILES:
        source = Path(filepath).read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "typing":
                imported_names = {alias.name for alias in node.names}
                old_names_found = imported_names & OLD_TYPING_NAMES
                assert not old_names_found, (
                    f"{filepath}:{node.lineno} imports old-style typing: "
                    f"{old_names_found}. Use built-in generics instead."
                )
```

**GREEN**: 执行上述替换。

**验收标准**:
- [ ] `grep "from typing import" tools/search_journals/keyword_pipeline.py` 如果有输出，则只包含 `Any`（没有 `Dict`, `List`, `Tuple`, `Optional`）
- [ ] 新 AST 测试通过
- [ ] 全量测试 0 failures
- [ ] mypy errors 不多于 13 个
- [ ] flake8 0 errors

**执行记录**:
```
（待填写）
```

---

### Task 4-2: schema.py 补全返回类型注解

**问题**: `tools/lib/schema.py` 的 `validate_metadata()` 和 `migrate_metadata()` 两个公开函数有参数类型注解但返回类型已标注（`-> List[Dict[str, str]]` 和 `-> Dict[str, Any]`），但使用了旧式泛型。同时需要验证文件内是否统一使用现代泛型。

**目标文件**: `tools/lib/schema.py`

**修改内容**:
1. 先阅读 `schema.py` 全文（109 行），检查所有函数签名的类型注解
2. 将旧式泛型替换为内建泛型（同 Task 4-1 的规则）
3. 确保所有公开函数（不以 `_` 开头的）都有返回类型注解

**RED**: 扩展 Task 4-1 的 `tests/unit/test_typing_modern.py`，将 `tools/lib/schema.py` 加入检查列表。另外添加：
```python
import inspect
from tools.lib import schema

def test_schema_public_functions_have_return_types():
    """schema.py 的所有公开函数必须有返回类型注解"""
    for name, func in inspect.getmembers(schema, inspect.isfunction):
        if name.startswith("_"):
            continue
        hints = func.__annotations__
        assert "return" in hints, (
            f"schema.{name}() 缺少返回类型注解"
        )
```

**GREEN**: 按需更新 `schema.py` 中的类型注解。

**验收标准**:
- [ ] `schema.py` 中所有公开函数有完整的参数和返回类型注解
- [ ] 无旧式 `typing.Dict` / `typing.List` 使用
- [ ] 新测试通过
- [ ] 全量测试 0 failures

**执行记录**:
```
（待填写）
```

---

### Phase 4 完成验收

```bash
python -m pytest tests/ -v --timeout=300 --benchmark-disable
mypy tools/ --ignore-missing-imports
flake8 tools/ web/ --count --max-complexity=40 --max-line-length=100

# 关键检查：
# 1. keyword_pipeline.py 中无旧式泛型
# 2. schema.py 所有公开函数有返回类型
# 3. mypy errors 不多于 13 个（理想情况可能减少）
```

---

## Phase 5: CI 加固 — P4

> **目标**: 让 CI 的检查从"形式存在"变为"真正有效"。
>
> **背景**: 审计发现 `coverage gate` 虽然在 `pyproject.toml` 中配置了 `fail_under = 70`，但 CI 从未真正检查。bandit 配置硬编码在 CLI 中，缺少文档化理由。

### Task 5-1: 添加 coverage gate 到 CI

**问题**: `pyproject.toml` line 202 设置了 `fail_under = 70`，但 `.github/workflows/ci.yml` 的 test job 没有实际运行 coverage 检查。

**目标文件**: `.github/workflows/ci.yml`

**修改内容**:
1. 在 `tests` job 的测试步骤中，将 `pytest` 调用改为带 coverage 的版本
2. 确保 `--cov-fail-under=70` 实际生效

**当前 CI 测试步骤大致为**:
```yaml
- name: Run tests
  run: |
    python -m pytest tests/ -v --timeout=300 --benchmark-disable
```

**修改为**:
```yaml
- name: Run tests with coverage
  run: |
    python -m pytest tests/ -v --timeout=300 --benchmark-disable --cov=tools --cov=web --cov-report=term-missing --cov-fail-under=70
```

⚠️ **执行前必须确认**:
1. `pyproject.toml` 的 `[tool.pytest.ini_options]` 中是否已配置了 `--cov` 相关选项（避免重复）
2. `pytest-cov` 是否已在 dev 依赖中（检查 `pyproject.toml` 的 `[project.optional-dependencies]` 或 `[tool.setuptools]`）
3. 如果 `pytest-cov` 不在依赖中，需要添加到 `[project.optional-dependencies] dev` 中

**RED**: 这个 Task 不需要新的 Python 测试（是 CI 配置变更）。验证方式：
```bash
# 本地模拟 CI 运行：
python -m pytest tests/ -v --timeout=300 --benchmark-disable --cov=tools --cov=web --cov-report=term-missing --cov-fail-under=70
```
如果本地跑的 coverage < 70%，则需要先确认真实覆盖率，再决定 `fail_under` 的合理值。

**GREEN**: 修改 `.github/workflows/ci.yml`

**验收标准**:
- [ ] CI 配置中有 `--cov-fail-under` 参数
- [ ] 本地 `python -m pytest ... --cov=tools --cov=web --cov-fail-under=70` 通过
- [ ] 如果覆盖率不足 70%，在执行记录中说明并调整 `fail_under` 到合理值
- [ ] 全量测试 0 failures

**执行记录**:
```
（待填写）
```

---

### Task 5-2: bandit 配置文件化 + B311 评估

**问题**: 当前 bandit 配置硬编码在 CI 命令中：`bandit -r tools/ -ll --skip B101,B311`。跳过 B311（弱随机数/弱哈希）没有文档化理由。

**目标文件**:
- 新建: `.bandit`（或在 `pyproject.toml` 中添加 `[tool.bandit]`）
- 修改: `.github/workflows/ci.yml`

**修改内容**:

**步骤 1**: 评估 B311 是否应该跳过
```bash
# 先看看不跳过 B311 时有多少告警
bandit -r tools/ -ll
```
如果 B311 告警全部来自非安全场景（如 `random.random()` 用于非加密用途），则跳过是合理的，但需要文档记录理由。如果有安全相关用途（如生成 token、password），则不应跳过。

**步骤 2**: 创建 bandit 配置

在 `pyproject.toml` 中添加：
```toml
[tool.bandit]
exclude_dirs = ["tests", "docs"]
skips = ["B101"]  # assert 语句，用于参数验证，非安全问题
# B311: 如果评估后确认可跳过，加入并附注释
# skips = ["B101", "B311"]  # B311: random 仅用于非加密场景（如序号生成）
```

**步骤 3**: 简化 CI 命令
```yaml
- name: Security scan with bandit
  run: |
    pip install bandit
    bandit -r tools/ -ll -c pyproject.toml
```

**RED**: 这个 Task 不需要新的 Python 测试。验证方式：
```bash
# 验证新配置是否与旧行为一致：
bandit -r tools/ -ll -c pyproject.toml
```

**验收标准**:
- [ ] `pyproject.toml` 中有 `[tool.bandit]` 配置段
- [ ] CI 中 bandit 命令使用 `-c pyproject.toml` 而非硬编码 `--skip`
- [ ] B311 的处理决定有文档记录（在 `pyproject.toml` 的注释中，或本 Task 的执行记录中）
- [ ] `bandit -r tools/ -ll -c pyproject.toml` 通过
- [ ] 全量测试 0 failures

**执行记录**:
```
（待填写）
```

---

### Phase 5 完成验收

```bash
python -m pytest tests/ -v --timeout=300 --benchmark-disable --cov=tools --cov=web --cov-report=term-missing --cov-fail-under=70
mypy tools/ --ignore-missing-imports
flake8 tools/ web/ --count --max-complexity=40 --max-line-length=100
bandit -r tools/ -ll -c pyproject.toml

# 关键检查：
# 1. CI 有 coverage gate 且本地验证通过
# 2. bandit 配置文件化
# 3. 全量测试 0 failures
```

---

## Phase 6: 测试完善 — P5

> **目标**: 补全审计发现的测试缺口，修正文档错误。

### Task 6-1: field_sources 专项 unit test

**问题**: `tools/write_journal/prepare.py` 的 `field_sources` 追踪机制（记录每个字段由用户/AI/规则填入）目前仅通过集成测试间接覆盖，没有专门的 unit test。

**目标文件**: 新建 `tests/unit/test_field_sources.py`

**修改内容**:

先阅读 `tools/write_journal/prepare.py` 中的 `field_sources` 相关逻辑，理解：
1. `field_sources` 的数据结构（预期为 `dict[str, str]`，value 为 `"user"` / `"ai"` / `"rule"` / `"default"`）
2. 哪些函数生成或修改 `field_sources`
3. 在什么条件下字段被标记为不同来源

**RED**: 
```python
def test_field_sources_user_provided_fields():
    """用户提供的字段应标记为 'user'"""
    # 用户提供了 title 和 tags
    raw = {"title": "我的标题", "content": "正文", "tags": "tag1, tag2"}
    result = prepare_journal_metadata(raw)  # 或对应函数名
    assert result["field_sources"]["title"] == "user"
    assert result["field_sources"]["tags"] == "user"

def test_field_sources_ai_generated_fields():
    """AI 自动生成的字段应标记为 'ai'"""
    # 用户只提供了 content，title 由 AI 生成
    raw = {"content": "这是一段很长的内容用于生成标题和摘要"}
    result = prepare_journal_metadata(raw)
    # title 和 abstract 应由 AI 或 fallback 生成
    assert result["field_sources"]["title"] in ("ai", "rule")
    assert result["field_sources"]["abstract"] in ("ai", "rule")

def test_field_sources_default_fields():
    """默认填充的字段应标记为 'default' 或 'rule'"""
    raw = {"title": "Test", "content": "内容"}
    result = prepare_journal_metadata(raw)
    # date 应有默认值
    assert "date" in result["field_sources"]

def test_field_sources_completeness():
    """field_sources 应覆盖所有输出的元数据字段"""
    raw = {"title": "Test", "content": "内容", "tags": "a, b"}
    result = prepare_journal_metadata(raw)
    # field_sources 的 key 集合应 >= 输出 metadata 的 key 集合
    metadata_keys = {k for k in result if k not in ("content", "field_sources")}
    source_keys = set(result.get("field_sources", {}).keys())
    missing = metadata_keys - source_keys
    assert not missing, f"field_sources 缺少以下字段的来源记录: {missing}"
```

⚠️ **注意**: 上面的函数名 `prepare_journal_metadata` 是推测。执行前必须阅读 `prepare.py` 确认实际函数名和签名。如果函数需要 LLM 调用，必须用 mock 替代。

**GREEN**: 如果测试发现 `field_sources` 不完整，需要修补 `prepare.py` 中的追踪逻辑。

**验收标准**:
- [ ] 至少 4 个 field_sources 相关测试
- [ ] 测试覆盖：user/ai/rule/default 四种来源
- [ ] 全量测试 0 failures

**执行记录**:
```
（待填写）
```

---

### Task 6-2: TDD 计划执行记录文档修正

**问题**: `docs/1.5.5/TDD_EXECUTION_PLAN.md` 中有文档错误：
1. Task 1A-1 的执行记录（line 180-185）引用了错误的 commit hash `ee2dcf7`（Phase 2B/2C），应为 `502a298`（Phase 1A/1B）
2. Task 5A-1 的执行记录（line 682-686）标记为 `❌ NOT_STARTED`，但实际上 commit `3d76931` 已完成了该任务

**目标文件**: `docs/1.5.5/TDD_EXECUTION_PLAN.md`

**修改内容**:

1. **Task 1A-1 执行记录**（约 line 179-185）:
   将
   ```
   ✅ DONE — 2026-03-29
   Commit: ee2dcf7 (included in Phase 2B/2C batch commit)
   Files: tools/search_journals/semantic.py, tools/lib/search_index.py, tools/search_journals/l3_content.py
   验证: 全量搜索测试通过
   ```
   改为
   ```
   ✅ DONE — 2026-03-29
   Commit: 502a298 (Phase 1A/1B)
   Files: tools/write_journal/prepare.py (新建), tools/lib/llm_extract.py (新建), tools/lib/text_normalize.py (新建), web/services/write.py (瘦身)
   验证: 全量测试通过
   ```

2. **Task 5A-1 执行记录**（约 line 682-686）:
   将
   ```
   ❌ NOT STARTED — 2026-03-29
   状态: 可选任务，非阻塞
   备注: pytest-benchmark 测试可在后续版本添加
   ```
   改为
   ```
   ✅ DONE — 2026-03-29
   Commit: 3d76931 (Phase 5A)
   Files: tests/benchmark/test_search_benchmark.py (新建, 470 lines), tests/benchmark/conftest.py (新建, 151 lines)
   新增: 16 个 benchmark 测试 (FTS5, RRF, keyword pipeline, semantic pipeline, hierarchical search)
   依赖: pyproject.toml 添加 pytest-benchmark>=4.0.0
   验证: pytest --benchmark-only 全部通过
   ```

**这个 Task 不需要 RED 测试**（纯文档修正）。

**验收标准**:
- [ ] Task 1A-1 执行记录引用 commit `502a298`
- [ ] Task 5A-1 执行记录标记为 `✅ DONE`，引用 commit `3d76931`
- [ ] 全量测试仍然 0 failures（确认未误改代码）

**执行记录**:
```
（待填写）
```

---

### Phase 6 完成验收

```bash
python -m pytest tests/ -v --timeout=300 --benchmark-disable
mypy tools/ --ignore-missing-imports
flake8 tools/ web/ --count --max-complexity=40 --max-line-length=100

# 关键检查：
# 1. field_sources 有专项测试
# 2. TDD 执行记录已修正
# 3. 全量测试 0 failures
```

---

## 附录 A: 文件变更预期总表

| 文件 | Phase | 变更类型 | 预期变化 |
|------|-------|----------|----------|
| `pyproject.toml` | 1-1, 5-1, 5-2 | 修改 | version bump + bandit 配置 + pytest-cov 依赖 |
| `docs/CHANGELOG.md` | 1-2 | 修改 | +10 行（FIX-10 补录） |
| `tools/lib/fts_search.py` | 1-3 | 修改 | 1 行（print→logger） |
| `tools/lib/fts_update.py` | 1-3 | 修改 | 1 行（print→logger） |
| `tools/search_journals/semantic_pipeline.py` | 2-1 | 修改 | 移除 Mock import，改判断逻辑 |
| `tools/write_journal/__main__.py` | 2-2 | 修改 | +1 行（logger.exception） |
| `tools/write_journal/prepare.py` | 2-2 | 修改 | +1 行（logger.warning） |
| `tools/lib/yaml_utils.py` | 3-1 | **新建** | ~50 行 |
| `tools/lib/paths.py` | 3-1 | 修改 | 移除重复函数，添加 import |
| `tools/lib/config.py` | 3-1 | 修改 | 移除重复函数，添加 import |
| `tools/search_journals/keyword_pipeline.py` | 4-1 | 修改 | typing 替换（~10 处） |
| `tools/lib/schema.py` | 4-2 | 修改 | 类型注解更新 |
| `.github/workflows/ci.yml` | 5-1, 5-2 | 修改 | coverage gate + bandit 配置引用 |
| `docs/1.5.5/TDD_EXECUTION_PLAN.md` | 6-2 | 修改 | 2 处执行记录修正 |

### 新建测试文件

| 文件 | Phase | 测试数 |
|------|-------|--------|
| `tests/unit/test_version_bump.py` | 1-1 | 1 |
| `tests/unit/test_fts_logging.py` | 1-3 | 2 |
| `tests/unit/test_semantic_pipeline_no_mock_import.py` | 2-1 | 2 |
| `tests/unit/test_exception_logging.py` | 2-2 | 2 |
| `tests/unit/test_yaml_utils.py` | 3-1 | 6 |
| `tests/unit/test_typing_modern.py` | 4-1, 4-2 | 3 |
| `tests/unit/test_field_sources.py` | 6-1 | 4+ |

---

## 附录 B: 风险与降级策略

| 风险 | 影响 | 降级策略 |
|------|------|----------|
| Mock import 移除后语义搜索判断逻辑变化 | 搜索降级行为改变 | 优先使用 `get_semantic_runtime_status()` 已有返回值；如果返回值不足，再扩展该函数 |
| yaml_utils 提取后调用链断裂 | paths/config 加载失败 | 全量测试覆盖；提取前先用 grep 确认所有调用方 |
| coverage gate 设置过高 | CI 红灯 | 先本地跑一次确认真实覆盖率，再设合理阈值 |
| 旧式泛型替换引起 mypy 行为变化 | 类型检查报错增加 | 替换前后各跑一次 mypy，对比错误数 |

---

## 附录 C: 执行检查清单（每个 Phase 完成后）

- [ ] 全量测试通过 (`python -m pytest tests/ -v --timeout=300 --benchmark-disable`)
- [ ] 类型检查通过 (`mypy tools/ --ignore-missing-imports`)，errors ≤ 13
- [ ] 代码风格通过 (`flake8 tools/ web/ --count --max-complexity=40 --max-line-length=100`)
- [ ] 无新增 `print()` 调用（`grep -rn "print(" tools/lib/ tools/search_journals/ tools/write_journal/ --include="*.py" | grep -v test | grep -v __pycache__`）
- [ ] 无新增 `# type: ignore` 或 `noqa`（除 `__init__.py` re-export 的 `noqa: F401`）
- [ ] Git commit（message 说明完成了哪些 Task）
- [ ] 更新本文档中对应 Task 的执行记录

---

## 附录 D: 本轮不处理的遗留项（仅记录）

> 以下问题在审计中被识别，但不在本轮 TDD 计划范围内。

### D.1 长函数拆分

| 函数 | 行数 | 建议 |
|------|------|------|
| `run_keyword_pipeline()` | 161 | 可提取 L1/L2/L3 各层为子函数 |
| `search_fts()` | 149 | 可提取查询构建和结果解析为子函数 |
| `update_index()` | 124 | 可提取文件解析和 DB 操作为子函数 |

**原因**: 函数虽长但内聚度高，拆分收益有限。优先级低于其他修复。

### D.2 Windows CI 真实路径测试

**问题**: Windows CI matrix 通过但所有 I/O 被 mock，不验证真实 Windows 路径。
**建议**: 添加 `@pytest.mark.windows` 标记的路径处理测试。
**原因**: 需要专门的 Windows 测试设计，超出本轮范围。

### D.3 Integration 测试目录重命名

**问题**: `tests/integration/` 中的测试实际上是重度 mock 化的 unit test。
**建议**: 考虑重新分类或重命名。
**原因**: 涉及大量测试文件移动，风险高，收益低。

### D.4 Benchmark 数据量扩展

**问题**: 当前 benchmark 使用 100-500 条数据，不能反映 10,000+ 条的真实场景。
**建议**: 添加 5,000-10,000 条数据的 benchmark。
**原因**: 需要生成大量测试数据，可能影响 CI 时间。

### D.5 SKILL.md 精简 [FIX-19]

**沿用上一轮 TDD 计划的延期决定**: 用户明确表示暂不修改。

### D.6 剩余 13 个 mypy 错误

**沿用上一轮 Appendix D.2 的记录**: `MODEL_CONFIG` object typing (8)、attachment list invariance (4)、operator types (2)。

---

> **文档结束**
>
> 本文档基于 v1.5.5 全面质量审计结果编写。
> 执行完成后，连同审计报告一起归档至 `docs/1.5.5/`。
