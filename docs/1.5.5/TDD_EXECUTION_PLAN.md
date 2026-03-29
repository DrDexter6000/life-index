# Life Index v1.5.5 TDD 执行计划

> **基于**: `docs/1.5.5/CTO_AUDIT_REPORT.md` (FIX-10 ~ FIX-21)
> **创建日期**: 2026-03-29
> **执行模式**: 由独立 Agent/LLM session 按 Phase → Batch → Task 顺序逐一执行
> **TDD 循环**: 每个 Task 严格遵循 Red → Green → Refactor
> **验收权威**: 以 `CTO_AUDIT_REPORT.md` §3 和 §7 的验收标准为最终裁判

---

## 执行须知（给执行 Agent 的指令）

### 开始前必读

1. **先读权威文档**：`docs/1.5.5/CTO_AUDIT_REPORT.md`（你在修什么、为什么修、验收标准是什么）
2. **先读架构文档**：`AGENTS.md`（CLI-as-SSOT 原则、Web 层约束、测试防污染规则）
3. **先读共享库指南**：`tools/lib/AGENTS.md`（`lib/` 模块约定）
4. **确认分支**：必须在 `1.5.5` 分支上工作（`git checkout 1.5.5`）

### TDD 循环（每个 Task 必须遵循）

```
1. RED:    写一个会失败的测试（验证目标行为不存在或当前行为错误）
2. GREEN:  写最少代码使测试通过
3. REFACTOR: 清理代码但不改变行为，确保测试仍通过
4. VERIFY: 运行完整测试套件确认无回归
```

### 验证命令

```bash
# 单元测试（快速，每个 task 完成后必跑）
python -m pytest tests/unit/ -v --timeout=60

# Contract 测试（涉及 Web-CLI 对齐时必跑）
python -m pytest tests/contract/ -v --timeout=60

# 集成测试（Phase 完成后跑）
python -m pytest tests/integration/ -v --timeout=300

# 全量测试（Phase 完成后跑）
python -m pytest tests/ -v --timeout=300

# 类型检查（每个 Phase 完成后跑）
mypy tools/ --ignore-missing-imports

# 代码风格检查
flake8 tools/ --count --max-complexity=40 --max-line-length=100
black --check tools/
```

### 执行记录格式

每完成一个 Task，在该 Task 的 `执行记录` 区块填写：

```
执行记录:
- 执行时间: YYYY-MM-DD HH:MM
- 执行 Agent/Session: [session ID 或标识]
- RED 测试文件: [新建/修改的测试文件路径]
- GREEN 实现: [修改的源文件路径和关键变更摘要]
- REFACTOR: [清理内容摘要，或 "无需重构"]
- 回归测试: ✅ 全部通过 / ❌ 失败 [详情]
- 备注: [遇到的问题、偏离计划的地方、后续需注意的点]
```

---

## 总览：Phase → Batch → Task

```
Phase 1 (P0): Web SSOT 修复 [FIX-10]
  ├── Batch 1A: CLI 层扩展 — 添加 Web 缺失的 CLI 能力
  ├── Batch 1B: Web 层瘦身 — 移除 Web 层业务逻辑
  └── Batch 1C: Contract 测试补全 — 证明格式一致性

Phase 2 (P1): 搜索核心重构 [FIX-11, FIX-12]
  ├── Batch 2A: Magic Numbers 集中管理 [FIX-12] — 先治理常量（不改行为）
  ├── Batch 2B: 搜索管道提取 [FIX-11] — 提取嵌套闭包为独立函数
  └── Batch 2C: 搜索降级警告 [FIX-16] — 添加 warnings 字段

Phase 3 (P2): 模块拆分 [FIX-13, FIX-14, FIX-15]
  ├── Batch 3A: config.py 拆分 [FIX-13]
  ├── Batch 3B: frontmatter.py 拆分 [FIX-14]
  └── Batch 3C: search_index.py 拆分 [FIX-15]

Phase 4 (P2): CI 补强 [FIX-17, FIX-18]
  ├── Batch 4A: 安全扫描 [FIX-17]
  └── Batch 4B: Windows CI [FIX-18]

Phase 5 (P3): 收尾 [FIX-19, FIX-20, FIX-21]
  ├── Batch 5A: 性能基准测试 [FIX-20]
  ├── Batch 5B: 代码异味清理 [FIX-21]
  └── Batch 5C: SKILL.md 精简 [FIX-19]
```

### 依赖关系

```
Phase 1 ──→ Phase 2（搜索重构依赖 SSOT 修复完成，因为 Web search service 也调用搜索）
Phase 2 ──→ Phase 3（模块拆分依赖搜索核心稳定）
Phase 3 ──→ Phase 4（CI 应在代码结构稳定后补强）
Phase 4 ──→ Phase 5（低优先级收尾最后做）
```

---

## Phase 1: Web SSOT 修复 [FIX-10] — P0

> **目标**: `web/services/` 不再包含任何业务逻辑（LLM 提取、天气查询、数据转换）。所有业务逻辑归 CLI 层。Web 写入与 CLI 写入产生 100% 相同的 frontmatter。
>
> **核心原则**: CLI 是 SSOT。Web 层只做表单收集 → CLI 调用 → 结果展示。
>
> **注意**: 这是最复杂的 Phase，因为涉及跨层重构。执行时务必保持 `write_journal()` 的公开接口不变。

### Batch 1A: CLI 层扩展 — 为 Web 流程补全 CLI 能力

> **指导思想**: 不是"把 Web 代码搬到 CLI"，而是"CLI 应该有哪些能力来服务 Web"。先扩展 CLI，再瘦身 Web。

#### Task 1A-1: CLI 层添加"原始输入预处理"入口

**背景**: 当前 `write_journal()` 接受已处理的数据。Web 层的 `prepare_journal_data()` 先做 LLM 提取 + 天气查询 + 字段规范化，然后才传给 `write_journal()`。这个"预处理"逻辑应在 CLI 层。

**目标文件**:
- 新建: `tools/write_journal/prepare.py`
- 修改: `tools/write_journal/__init__.py`（re-export）

**RED**: 新建 `tests/unit/test_write_journal_prepare.py`
```python
def test_prepare_normalizes_tags_from_string():
    """逗号分隔字符串应转为列表"""
    raw = {"title": "Test", "content": "内容", "tags": "tag1, tag2, tag3"}
    prepared = prepare_raw_input(raw)
    assert prepared["tags"] == ["tag1", "tag2", "tag3"]

def test_prepare_normalizes_mood_from_string():
    raw = {"title": "Test", "content": "内容", "mood": "开心, 充实"}
    prepared = prepare_raw_input(raw)
    assert prepared["mood"] == ["开心", "充实"]

def test_prepare_preserves_list_input():
    """已经是列表的输入应原样保留"""
    raw = {"title": "Test", "content": "内容", "tags": ["tag1", "tag2"]}
    prepared = prepare_raw_input(raw)
    assert prepared["tags"] == ["tag1", "tag2"]

def test_prepare_infers_project():
    """有已知别名时应推断项目"""
    raw = {"title": "Test", "content": "内容", "tags": ["LifeIndex", "优化"]}
    prepared = prepare_raw_input(raw)
    assert prepared.get("project") is not None

def test_prepare_generates_fallback_title():
    """无标题时应生成回退标题"""
    raw = {"content": "这是一段很长的内容，足够生成标题"}
    prepared = prepare_raw_input(raw)
    assert prepared["title"]  # 非空

def test_prepare_generates_fallback_abstract():
    """无摘要时应生成回退摘要"""
    raw = {"title": "Test", "content": "这是一段内容"}
    prepared = prepare_raw_input(raw)
    assert prepared.get("abstract")
```

**GREEN**: 实现 `tools/write_journal/prepare.py`:
- `prepare_raw_input(raw_data: dict) -> dict` — 规范化所有列表字段（tags, mood, topic, people）
- `_normalize_text_list(value)` — 从 `web/services/write.py` 迁移（不是复制）
- `_infer_project(tags, content)` — 从 `web/services/write.py` 迁移
- `_fallback_title(content)` — 从 `web/services/write.py` 迁移
- `_fallback_abstract(content)` — 从 `web/services/write.py` 迁移
- `KNOWN_PROJECT_ALIASES` — 从 `web/services/write.py` 迁移

**验收**:
- `prepare_raw_input()` 可独立调用、独立测试
- 函数签名不依赖任何 Web 框架
- 所有列表字段的规范化走同一路径

**执行记录**:
```
（由执行 Agent 填写）
```

---

#### Task 1A-2: CLI 层添加"LLM 元数据提取"能力

**背景**: 当前 LLM 提取逻辑全在 `web/services/llm_provider.py`（650 行）。这是核心业务逻辑，必须在 CLI 层。

**目标文件**:
- 新建: `tools/write_journal/llm_extract.py`
- 迁移源: `web/services/llm_provider.py`

**RED**: 新建 `tests/unit/test_write_journal_llm_extract.py`
```python
def test_extract_metadata_returns_expected_fields(mock_llm):
    """LLM 提取应返回标准字段集"""
    result = extract_metadata("今天去公园散步，天气很好")
    assert "title" in result
    assert "tags" in result
    assert "mood" in result
    assert "abstract" in result

def test_extract_metadata_handles_llm_failure():
    """LLM 不可用时应返回空 dict（不崩溃）"""
    result = extract_metadata("内容", llm_available=False)
    assert result == {} or result.get("error")

def test_extract_metadata_validates_topic():
    """提取的 topic 必须在 VALID_TOPICS 内"""
    result = extract_metadata("工作相关内容")
    if "topic" in result:
        valid = {"work", "learn", "health", "relation", "think", "create", "life"}
        for t in (result["topic"] if isinstance(result["topic"], list) else [result["topic"]]):
            assert t in valid

def test_parse_json_strips_think_blocks():
    """LLM 返回中的 <think> 块应被移除"""
    raw = '<think>reasoning</think>{"title": "Test"}'
    parsed = parse_llm_json_response(raw)
    assert parsed == {"title": "Test"}
```

**GREEN**: 实现 `tools/write_journal/llm_extract.py`:
- `extract_metadata(content: str, **kwargs) -> dict` — 公共接口
- `parse_llm_json_response(raw: str) -> dict` — JSON 解析（迁移自 `llm_provider.py` 的 `_parse_json_object_from_text`）
- `EXTRACTION_SYSTEM_PROMPT` — 迁移自 `llm_provider.py`
- `VALID_TOPICS` — 迁移自 `llm_provider.py`
- LLM 调用抽象接口（可插入不同 provider）

**关键约束**:
- 这个模块不依赖 Web 框架
- LLM provider 通过依赖注入（函数参数或策略模式），不硬编码
- 失败时返回空 dict，不抛异常（由调用方决定降级策略）

**执行记录**:
```
（由执行 Agent 填写）
```

---

#### Task 1A-3: CLI 层统一"天气查询 + 位置解析"流程

**背景**: 天气查询逻辑在两处重复：`tools/write_journal/weather.py` 和 `web/services/write.py` (lines 268-301)。Web 还添加了浏览器 geolocation 解析（`web/services/geolocation.py`）。

**目标文件**:
- 修改: `tools/write_journal/weather.py`（扩展，添加坐标输入支持）
- 保留: `web/services/geolocation.py`（浏览器 geolocation 是纯 Web 能力，可保留在 Web 层，但只负责坐标获取，位置解析交 CLI）

**RED**: 扩展 `tests/unit/test_query_weather.py`
```python
def test_weather_accepts_coordinates():
    """CLI 天气查询应支持经纬度输入"""
    result = query_weather_for_location(lat=6.5244, lon=3.3792)
    # 应返回位置名 + 天气（或 mock）

def test_weather_normalizes_location_string():
    """位置字符串应被规范化（去空格、统一大小写等）"""
    loc1 = normalize_location("  Lagos , Nigeria  ")
    loc2 = normalize_location("Lagos,Nigeria")
    assert loc1 == loc2

def test_weather_compact_location():
    """应返回紧凑位置格式"""
    compact = compact_location("Lagos, Lagos State, Nigeria")
    assert compact == "Lagos, Nigeria"  # 或合理的紧凑格式
```

**GREEN**: 扩展 `tools/write_journal/weather.py`:
- 添加 `lat`/`lon` 参数支持到 `query_weather_for_location()`
- 迁移 `_compact_location()` 从 `web/services/write.py`
- 迁移 `_extract_weather_text()` 从 `web/services/write.py`（如果 CLI 层尚未有等效实现）

**执行记录**:
```
（由执行 Agent 填写）
```

---

#### Task 1A-4: CLI 层添加"Web 写入一站式入口"

**背景**: Web 层需要一个 CLI 入口，接受原始表单数据（包含可能的坐标、附件暂存路径），完成全部预处理后写入。这是 Web→CLI 的唯一入口。

**目标文件**:
- 修改: `tools/write_journal/core.py`（添加 `write_journal_from_raw()` 或扩展 `write_journal()` 参数）

**RED**: 扩展 `tests/unit/test_write_journal_core.py`
```python
def test_write_from_raw_handles_string_tags(temp_data_dir):
    """原始输入的 string tags 应被规范化写入"""
    result = write_journal({"title": "Test", "content": "内容", "tags": "tag1, tag2"})
    fm = parse_frontmatter(Path(result["journal_path"]).read_text(encoding="utf-8"))[0]
    assert fm["tags"] == ["tag1", "tag2"]

def test_write_from_raw_with_llm_extraction(temp_data_dir, mock_llm):
    """原始内容应经过 LLM 提取填充元数据"""
    result = write_journal({"content": "今天去公园散步，心情很好"}, enrich=True)
    fm = parse_frontmatter(Path(result["journal_path"]).read_text(encoding="utf-8"))[0]
    assert fm.get("title")  # LLM 或 fallback 应生成标题

def test_write_from_raw_with_weather(temp_data_dir, mock_weather):
    """传入位置时应查询天气"""
    result = write_journal(
        {"title": "Test", "content": "内容", "location": "Lagos,Nigeria"},
        enrich=True
    )
    fm = parse_frontmatter(Path(result["journal_path"]).read_text(encoding="utf-8"))[0]
    assert fm.get("weather")
```

**GREEN**: 修改 `tools/write_journal/core.py`:
- `write_journal()` 添加 `enrich: bool = False` 参数
- 当 `enrich=True` 时调用 `prepare_raw_input()` → `extract_metadata()` → `query_weather_for_location()`
- 当 `enrich=False` 时保持现有行为（向后兼容）

**关键约束**:
- `write_journal()` 的现有调用方不受影响（`enrich` 默认 False）
- 新流程：`raw data → prepare_raw_input() → [optional: extract_metadata()] → [optional: query_weather()] → write_journal()`

**执行记录**:
```
（由执行 Agent 填写）
```

---

### Batch 1B: Web 层瘦身 — 移除 Web 层业务逻辑

> **指导思想**: CLI 能力就绪后，Web 层逐步"掏空"为薄壳。每步验证 contract tests 仍通过。

#### Task 1B-1: Web write service 改为调用 CLI `write_journal(enrich=True)`

**背景**: `web/services/write.py::prepare_journal_data()` 的 341 行中，大部分业务逻辑已迁移到 CLI。现在让 Web 直接调用 CLI 入口。

**目标文件**:
- 重写: `web/services/write.py`（从 341 行瘦身到 ~80 行）
- 删除: `web/services/llm_provider.py`（650 行 → 删除或保留为 Web 层 LLM provider 薄壳）

**RED**: 修改 `tests/unit/test_web_write.py`
```python
def test_web_write_delegates_to_cli(mock_write_journal):
    """Web 写入必须调用 CLI write_journal，不自己做业务逻辑"""
    # 验证 web write service 调用了 write_journal(enrich=True)
    # 而不是自己调用 llm_provider、query_weather 等

def test_web_write_no_normalize_text_list():
    """web/services/write.py 不应包含 _normalize_text_list 函数"""
    import web.services.write as ws
    assert not hasattr(ws, "_normalize_text_list")

def test_web_write_no_infer_project():
    """web/services/write.py 不应包含 _infer_project 函数"""
    import web.services.write as ws
    assert not hasattr(ws, "_infer_project")
```

**GREEN**: 重写 `web/services/write.py`:
- `prepare_journal_data()` → 删除，或简化为仅收集表单字段
- `write_journal_web()` → 直接调用 `write_journal(data, enrich=True)`
- 删除所有 `_normalize_*`、`_infer_*`、`_fallback_*`、`_compact_*`、`_extract_*` 函数
- 如果 Web 需要"预览 LLM 提取结果"的 AJAX 流程，可新增薄封装 `preview_metadata()` → 调用 CLI 的 `extract_metadata()`

**验证**:
```bash
python -m pytest tests/contract/test_web_cli_alignment.py -v
python -m pytest tests/unit/test_web_write.py -v
```

**执行记录**:
```
（由执行 Agent 填写）
```

---

#### Task 1B-2: Web edit service 移除 diff 计算逻辑

**背景**: `web/services/edit.py::compute_edit_diff()` 是业务逻辑，应在 CLI 层。

**目标文件**:
- 修改: `web/services/edit.py`（从 154 行瘦身到 ~40 行）
- 修改: `tools/edit_journal/__init__.py`（添加 diff 计算能力，如果尚无）

**RED**: 
```python
def test_web_edit_no_compute_edit_diff():
    """web/services/edit.py 不应包含 compute_edit_diff"""
    import web.services.edit as we
    assert not hasattr(we, "compute_edit_diff")

def test_cli_edit_handles_diff_computation(temp_data_dir):
    """CLI edit 应能接受 original + submitted 并计算差异"""
    # 测试 CLI 层的 diff 能力
```

**GREEN**: 
- 迁移 `compute_edit_diff()` 到 `tools/edit_journal/diff.py`
- `web/services/edit.py` 只保留 `edit_journal_web()` 薄封装

**执行记录**:
```
（由执行 Agent 填写）
```

---

#### Task 1B-3: 清理 Web 层 LLM Provider

**背景**: `web/services/llm_provider.py`（650 行）是最大的 SSOT 违规源。LLM 提取核心已迁移到 CLI (Task 1A-2)。

**目标文件**:
- 删除或大幅瘦身: `web/services/llm_provider.py`
- 如果 Web 需要自己的 provider 选择逻辑（如 API key vs Host Agent），保留 ~50 行 adapter

**RED**: 
```python
def test_web_llm_provider_no_extraction_prompt():
    """web/services/llm_provider.py 不应包含 EXTRACTION_SYSTEM_PROMPT"""
    import web.services.llm_provider as lp
    assert not hasattr(lp, "EXTRACTION_SYSTEM_PROMPT")

def test_web_llm_provider_no_parse_json():
    """web/services/llm_provider.py 不应包含 _parse_json_object_from_text"""
    import web.services.llm_provider as lp
    assert not hasattr(lp, "_parse_json_object_from_text")
```

**GREEN**: 删除 `EXTRACTION_SYSTEM_PROMPT`、`_parse_json_object_from_text`、`VALID_TOPICS` 及所有 JSON 解析逻辑。如果保留文件，只保留 provider 注册/选择的薄壳。

**执行记录**:
```
（由执行 Agent 填写）
```

---

### Batch 1C: Contract 测试补全

> **指导思想**: 新增 contract tests 覆盖所有重构后的对齐点。

#### Task 1C-1: 补全 Web-CLI 格式对齐 contract tests

**目标文件**: `tests/contract/test_web_cli_alignment.py`

**当前覆盖**（4 个测试）:
- ✅ tags 数组格式
- ✅ mood 数组格式
- ✅ edit 保留数组格式
- ✅ attachment 格式

**需新增**:
```python
def test_weather_format_alignment(temp_data_dir, mock_weather):
    """Web 和 CLI 写入的 weather 字段格式必须一致"""

def test_llm_extracted_fields_alignment(temp_data_dir, mock_llm):
    """LLM 提取的 title/abstract/tags/mood 格式必须一致"""

def test_project_inference_alignment(temp_data_dir):
    """Web 和 CLI 的 project 推断结果必须一致"""

def test_topic_format_alignment(temp_data_dir):
    """topic 字段格式（数组）必须一致"""

def test_people_format_alignment(temp_data_dir):
    """people 字段格式必须一致"""

def test_frontmatter_field_order_alignment(temp_data_dir):
    """frontmatter 字段顺序必须遵循 FIELD_ORDER"""
```

**执行记录**:
```
（由执行 Agent 填写）
```

---

### Phase 1 完成验收

```bash
# 必须全部通过
python -m pytest tests/ -v --timeout=300
mypy tools/ --ignore-missing-imports
flake8 tools/ --count --max-complexity=40 --max-line-length=100

# 关键指标
# 1. web/services/write.py 行数 < 100
# 2. web/services/llm_provider.py 行数 < 100（或已删除）
# 3. web/services/edit.py 行数 < 50
# 4. tests/contract/test_web_cli_alignment.py 测试数 >= 10
# 5. 零 contract test 失败
```

---

## Phase 2: 搜索核心重构 [FIX-11, FIX-12, FIX-16] — P1

> **目标**: 搜索管道可独立测试；所有 magic numbers 集中管理；搜索降级可观测。
>
> **执行顺序**: 先 FIX-12（常量治理，纯重构不改行为）→ FIX-11（函数提取）→ FIX-16（添加 warnings）
>
> **核心约束**: 搜索行为不变。全量搜索测试（unit + integration + contract）必须始终通过。

### Batch 2A: Magic Numbers 集中管理 [FIX-12]

> **指导思想**: 纯重构 — 提取常量到集中位置，不改任何逻辑。每步之后搜索行为不变。

#### Task 2A-1: 创建 `tools/lib/search_constants.py`

**目标文件**: 新建 `tools/lib/search_constants.py`

**RED**:
```python
# tests/unit/test_search_constants.py
def test_all_search_constants_have_docstring():
    """每个常量必须有注释说明选择理由"""
    import tools.lib.search_constants as sc
    # 验证模块 docstring 存在
    assert sc.__doc__

def test_rrf_k_is_60():
    from tools.lib.search_constants import RRF_K
    assert RRF_K == 60

def test_semantic_min_similarity():
    from tools.lib.search_constants import SEMANTIC_MIN_SIMILARITY
    assert SEMANTIC_MIN_SIMILARITY == 0.15

def test_fts_min_relevance():
    from tools.lib.search_constants import FTS_MIN_RELEVANCE
    assert FTS_MIN_RELEVANCE == 25
```

**GREEN**: 新建 `tools/lib/search_constants.py`:
```python
"""
搜索算法常量集中定义。

每个常量附 ADR-style 选择理由。修改任一常量前，请先跑 tests/unit/test_search_constants.py
和 tests/integration/test_search_pipeline.py 确认无回归。
"""

# === RRF 融合 ===
RRF_K: int = 60
"""RRF 平滑常数。k=60 来自 Cormack et al. SIGIR 2009 推荐值。
k 越低排名差异越激进，k 越高越平滑。60 是通用场景推荐值。"""

# === 语义搜索 ===
SEMANTIC_TOP_K: int = 30
"""语义搜索召回量。30 在个人日志规模（<10K）下提供足够覆盖。"""

SEMANTIC_MIN_SIMILARITY: float = 0.15
"""语义最低相似度阈值。低于此值的结果被过滤。
0.15 对 MiniLM-L6-v2 384d 模型，经验证是噪声/信号分界点。"""

# === FTS (全文搜索) ===
FTS_MIN_RELEVANCE: int = 25
"""FTS5 BM25 最低相关度。relevance = max(0, min(100, 70 - bm25_score * 5))。
25 以下多为噪声匹配。"""

FTS_SEARCH_LIMIT: int = 100
"""FTS SQL 查询 LIMIT。召回候选集上限。"""

FTS_FALLBACK_THRESHOLD: int = 5
"""FTS 结果少于此数量时触发兜底全文扫描。"""

# === 分数阈值 ===
RRF_MIN_SCORE: float = 0.008
"""RRF 融合后最低保留分。低于此值的结果被丢弃。"""

NON_RRF_MIN_SCORE: float = 10
"""非 RRF 模式（纯关键词）最低保留分。"""

MAX_SEARCH_RESULTS: int = 20
"""最终返回给调用方的最大结果数。"""

# === 层级评分 ===
L1_BASE_SCORE: float = 10.0
"""L1 索引匹配基础分。"""

L2_BASE_SCORE: float = 20.0
"""L2 元数据匹配基础分。"""

TITLE_MATCH_BONUS: float = 8.0
"""标题匹配加分。"""

ABSTRACT_MATCH_BONUS: float = 4.0
"""摘要匹配加分。"""

TAGS_MATCH_BONUS: float = 1.0
"""标签匹配加分（每个匹配标签）。"""

FTS_TITLE_MATCH_BONUS: float = 10.0
"""FTS title_match 额外加分。"""

SEMANTIC_TIER: int = 4
"""语义结果在 tiered ranking 中的层级编号。"""

BACKFILL_TARGET: int = 3
"""结果不足时的回填目标数量。"""

# === BM25 转换 ===
BM25_BASE: int = 70
"""BM25 → 0-100 转换基础值。"""

BM25_SCALE: int = 5
"""BM25 → 0-100 转换缩放因子。公式: relevance = max(0, min(100, BM25_BASE - bm25_score * BM25_SCALE))"""
```

**验证**: 全量搜索测试不变
```bash
python -m pytest tests/unit/test_search_* tests/integration/test_search_pipeline.py tests/contract/test_search_contract.py -v
```

**执行记录**:
```
（由执行 Agent 填写）
```

---

#### Task 2A-2: 替换 core.py 和 ranking.py 中的硬编码值

**目标文件**:
- `tools/search_journals/core.py`（替换 lines 167-171, 263, 335, 368 的硬编码值）
- `tools/search_journals/ranking.py`（替换 lines 48, 77-78, 108, 121-122, 125, 139, 174-176, 200, 212, 253, 263, 283, 295-296, 298, 319, 338-340, 354 的硬编码值）

**RED**: 运行现有搜索测试套件确认当前状态
```bash
python -m pytest tests/unit/test_search_journals_core.py tests/unit/test_search_ranking.py tests/integration/test_search_pipeline.py -v
```

**GREEN**: 逐一替换硬编码值为 `search_constants.py` 的常量引用。**一次替换一个文件，每次替换后跑测试。**

**关键**: 函数参数的默认值也应引用常量：
```python
# BEFORE
def hierarchical_search(..., semantic_top_k: int = 30, ...):
# AFTER
from ..lib.search_constants import SEMANTIC_TOP_K
def hierarchical_search(..., semantic_top_k: int = SEMANTIC_TOP_K, ...):
```

**验证**: 每次替换后全量搜索测试必须通过（行为不变）

**执行记录**:
```
（由执行 Agent 填写）
```

---

#### Task 2A-3: 替换 semantic.py, search_index.py, l3_content.py 中的硬编码值

**目标文件**:
- `tools/search_journals/semantic.py`（lines 50-51: 修复 top_k=50 → 应与 core.py 一致用 SEMANTIC_TOP_K）
- `tools/lib/search_index.py`（lines 276-277, 336, 384）
- `tools/search_journals/l3_content.py`（lines 21-23, 74）

**特别注意**: `semantic.py` 的 `top_k=50` 与 `core.py` 的 `semantic_top_k=30` 不一致。统一为 `SEMANTIC_TOP_K` 后，确认集成测试仍通过。如果行为变化，在测试中记录。

**执行记录**:
```
（由执行 Agent 填写）
```

---

### Batch 2B: 搜索管道提取 [FIX-11]

> **指导思想**: 将嵌套闭包提取为模块级函数，使其可独立测试。`hierarchical_search()` 只负责编排。

#### Task 2B-1: 提取 `pipeline_keyword()` 为模块级函数

**背景**: `pipeline_keyword()` 定义在 `core.py` 的 `hierarchical_search()` 内部（lines 258-411），154 行，通过闭包捕获 `query`, `topic`, `tags`, `project`, `people`, `date_range`, `fts_min_relevance` 等变量。

**目标文件**:
- 修改: `tools/search_journals/core.py`
- 新建（可选）: `tools/search_journals/keyword_pipeline.py`

**RED**: 新建 `tests/unit/test_keyword_pipeline.py`
```python
def test_keyword_pipeline_returns_ranked_results(temp_search_index):
    """独立调用 keyword pipeline 应返回排序后的结果"""
    results = run_keyword_pipeline(
        query="测试查询",
        topic=["work"],
        tags=[],
        fts_min_relevance=25,
    )
    assert isinstance(results, list)

def test_keyword_pipeline_empty_query(temp_search_index):
    """空查询应返回空列表（或仅靠 metadata 过滤）"""
    results = run_keyword_pipeline(query="", topic=["work"])
    assert isinstance(results, list)

def test_keyword_pipeline_l1_l2_l3_progression(temp_search_index):
    """应按 L1→L2→L3 逐层搜索"""
    results = run_keyword_pipeline(query="存在的关键词", topic=["work"])
    # 验证结果来自预期层级

def test_keyword_pipeline_fts_fallback(temp_search_index):
    """FTS 结果不足时应触发兜底"""
    # 构造只有少量 FTS 命中的场景
```

**GREEN**: 提取 `pipeline_keyword()` 为模块级函数：
```python
def run_keyword_pipeline(
    query: str,
    topic: list[str] | None = None,
    tags: list[str] | None = None,
    project: str | None = None,
    people: list[str] | None = None,
    date_range: tuple | None = None,
    fts_min_relevance: int = FTS_MIN_RELEVANCE,
    # ... 所有原来通过闭包捕获的变量改为显式参数
) -> list[dict]:
```

**关键约束**:
- 参数签名必须包含所有原来通过闭包捕获的变量
- `hierarchical_search()` 调用 `run_keyword_pipeline()` 替代内部闭包
- 行为不变：全量搜索测试通过

**执行记录**:
```
（由执行 Agent 填写）
```

---

#### Task 2B-2: 提取 `pipeline_semantic()` 为模块级函数

**背景**: `pipeline_semantic()` 定义在 `core.py` lines 413-445，33 行，相对简单。

**目标文件**: `tools/search_journals/core.py`（或 `semantic.py`）

**RED**: 新建/扩展 `tests/unit/test_semantic_pipeline.py`
```python
def test_semantic_pipeline_returns_scored_results(temp_vector_index):
    """独立调用 semantic pipeline 应返回带分数的结果"""

def test_semantic_pipeline_handles_unavailable_model():
    """模型不可用时应返回空列表 + 原因"""

def test_semantic_pipeline_respects_min_similarity():
    """低于 min_similarity 的结果应被过滤"""
```

**GREEN**: 提取为模块级函数，显式参数传递。

**执行记录**:
```
（由执行 Agent 填写）
```

---

#### Task 2B-3: 瘦身 `hierarchical_search()` 为编排入口

**目标**: `hierarchical_search()` 从 ~362 行缩减到 ~100 行，只负责：
1. 参数验证
2. 根据 level 选择执行路径
3. Level 3: 并行调度 keyword + semantic pipeline
4. RRF 融合
5. 返回结果

**RED**: 现有测试应全部通过（无行为变更）
```bash
python -m pytest tests/unit/test_search_journals_core.py tests/integration/test_search_pipeline.py -v
```

**GREEN**: 重构 `hierarchical_search()`:
- Level 1/2 路径保持不变（已经是独立函数 `_search_level_1`, `_search_level_2`）
- Level 3 路径改为调用 `run_keyword_pipeline()` 和 `run_semantic_pipeline()`
- RRF 融合调用 `ranking.py` 的现有函数

**验收**: `hierarchical_search()` 函数体 ≤ 100 行

**执行记录**:
```
（由执行 Agent 填写）
```

---

### Batch 2C: 搜索降级警告 [FIX-16]

#### Task 2C-1: 返回值添加 `warnings` 字段

**背景**: 当前语义搜索失败时静默返回空列表。调用方无法区分"零结果"和"搜索降级"。

**目标文件**:
- `tools/search_journals/core.py`（返回值添加 `warnings` 字段）
- `tools/search_journals/semantic.py`（lines 105-107: 捕获异常后返回原因）

**RED**: 
```python
# tests/unit/test_search_degradation.py
def test_search_returns_warnings_field():
    """搜索结果必须包含 warnings 字段"""
    result = hierarchical_search(query="test", level=3)
    assert "warnings" in result
    assert isinstance(result["warnings"], list)

def test_semantic_unavailable_produces_warning(mock_semantic_unavailable):
    """语义搜索不可用时，warnings 应包含原因"""
    result = hierarchical_search(query="test", level=3)
    assert any("semantic" in w.lower() for w in result["warnings"])

def test_warnings_empty_when_all_pipelines_ok():
    """所有管道正常时，warnings 应为空列表"""
    result = hierarchical_search(query="test", level=3)
    assert result["warnings"] == []
```

**GREEN**:
1. `semantic.py`: 异常时返回 `([], error_reason: str)` 而非仅 `[]`
2. `core.py`: 收集 pipeline 警告信息，添加到返回值的 `warnings` 字段
3. 返回值格式向后兼容（`warnings` 是新增字段）

**关键**: 检查并更新 `docs/API.md` 中搜索返回值的文档。

**执行记录**:
```
（由执行 Agent 填写）
```

---

### Phase 2 完成验收

```bash
python -m pytest tests/ -v --timeout=300
mypy tools/ --ignore-missing-imports

# 关键指标
# 1. hierarchical_search() 行数 ≤ 100
# 2. pipeline_keyword/semantic 可独立 import 和测试
# 3. 所有 magic numbers 在 search_constants.py 集中定义
# 4. 搜索降级时 warnings 字段非空
# 5. 零测试失败
```

---

## Phase 3: 模块拆分 [FIX-13, FIX-14, FIX-15] — P2

> **目标**: 每个源文件 ≤ 300 行。拆分后通过 `__init__.py` re-export 保持导入兼容。
>
> **核心约束**: SSOT 语义不变。`from tools.lib.frontmatter import parse_frontmatter` 等现有导入路径必须继续工作。

### Batch 3A: config.py 拆分 [FIX-13]

#### Task 3A-1: 提取路径管理到 `tools/lib/paths.py`

**提取内容**: `resolve_user_data_dir()`, `resolve_journals_dir()`, `ensure_dirs()`, 路径常量（USER_DATA_DIR, JOURNALS_DIR, BY_TOPIC_DIR 等）, `get_journal_dir()`, `get_next_sequence()`, `normalize_path()`, `get_safe_path()`

**RED**: 
```python
def test_paths_importable():
    from tools.lib.paths import USER_DATA_DIR, JOURNALS_DIR
    assert USER_DATA_DIR
    assert JOURNALS_DIR

def test_config_reexports_paths():
    """config.py 必须 re-export 路径常量（向后兼容）"""
    from tools.lib.config import USER_DATA_DIR, JOURNALS_DIR
    from tools.lib.paths import USER_DATA_DIR as P_UDD
    assert USER_DATA_DIR == P_UDD
```

**GREEN**: 
1. 新建 `tools/lib/paths.py`，移入路径相关代码
2. `config.py` 添加 `from .paths import *`（re-export）
3. `tools/lib/__init__.py` 添加 re-export

**验证**: 全量测试通过，无 import 错误

**执行记录**:
```
（由执行 Agent 填写）
```

---

#### Task 3A-2: 提取搜索配置到 `tools/lib/search_config.py`

**提取内容**: `get_search_config()`, `get_search_weights()`, `save_search_weights()`, `get_search_mode()`, `save_search_mode()`, 以及嵌入模型配置 `EMBEDDING_MODEL`, `get_model_cache_dir()`

**执行记录**:
```
（由执行 Agent 填写）
```

---

#### Task 3A-3: 验证 config.py 瘦身结果

**验收**: `config.py` 行数 ≤ 300，每个拆分文件 ≤ 300 行

**执行记录**:
```
（由执行 Agent 填写）
```

---

### Batch 3B: frontmatter.py 拆分 [FIX-14]

#### Task 3B-1: 提取附件处理到 `tools/lib/attachment.py`

**提取内容**: `normalize_attachment_entries()`, `_normalize_attachment_write_input()`, `_guess_attachment_content_type()`, `_normalize_attachment_stored_metadata()` (~87 行)

**RED**: 
```python
def test_attachment_importable():
    from tools.lib.attachment import normalize_attachment_entries
    assert callable(normalize_attachment_entries)

def test_frontmatter_reexports_attachment():
    """frontmatter.py 必须 re-export（向后兼容）"""
    from tools.lib.frontmatter import normalize_attachment_entries
    assert callable(normalize_attachment_entries)
```

**执行记录**:
```
（由执行 Agent 填写）
```

---

#### Task 3B-2: 提取验证/迁移到 `tools/lib/schema.py`

**提取内容**: `validate_metadata()`, `migrate_metadata()`, `get_schema_version()`, `get_required_fields()`, `get_recommended_fields()` (~94 行)

**执行记录**:
```
（由执行 Agent 填写）
```

---

#### Task 3B-3: 验证 frontmatter.py 瘦身结果

**验收**: `frontmatter.py` 行数 ≤ 300

**执行记录**:
```
（由执行 Agent 填写）
```

---

### Batch 3C: search_index.py 拆分 [FIX-15]

#### Task 3C-1: 提取 FTS 搜索到 `tools/lib/fts_search.py`

**提取内容**: `search_fts()` (~141 行，含两个查询变体)

**额外改进**: 合并两个查询变体（有/无 mood/people 列）为单一查询方法，减少代码重复。

**执行记录**:
```
（由执行 Agent 填写）
```

---

#### Task 3C-2: 提取索引更新到 `tools/lib/fts_update.py`

**提取内容**: `update_index()`, `get_indexed_files()`, `parse_journal()`, `get_file_hash()`, `_normalize_to_str()` (~134 行)

**执行记录**:
```
（由执行 Agent 填写）
```

---

#### Task 3C-3: 验证 search_index.py 瘦身结果

**验收**: `search_index.py` 行数 ≤ 300 (保留 init_fts_db + get_stats + re-exports)

**执行记录**:
```
（由执行 Agent 填写）
```

---

### Phase 3 完成验收

```bash
python -m pytest tests/ -v --timeout=300
mypy tools/ --ignore-missing-imports

# 关键指标
# 1. tools/lib/config.py ≤ 300 行
# 2. tools/lib/frontmatter.py ≤ 300 行
# 3. tools/lib/search_index.py ≤ 300 行
# 4. 所有现有 import 路径仍可工作（re-export）
# 5. 零测试失败
```

---

## Phase 4: CI 补强 [FIX-17, FIX-18] — P2

### Batch 4A: 安全扫描 [FIX-17]

#### Task 4A-1: CI 添加 Bandit 安全扫描

**目标文件**: `.github/workflows/ci.yml`

**实现**:
1. 在 `lint` job 中添加 bandit 步骤
2. `pip install bandit`
3. `bandit -r tools/ -c pyproject.toml`（或 `-ll` 低置信度过滤）
4. 在 `pyproject.toml` 中添加 bandit 配置（排除测试目录等）

**验收**: CI 中 bandit 步骤通过

**执行记录**:
```
（由执行 Agent 填写）
```

---

### Batch 4B: Windows CI [FIX-18]

#### Task 4B-1: CI 添加 Windows 测试矩阵

**目标文件**: `.github/workflows/ci.yml`

**实现**:
1. `tests` job 的 `strategy.matrix` 添加 `os: [ubuntu-latest, windows-latest]`
2. 处理 Windows 特有问题：
   - 路径分隔符（`\` vs `/`）
   - `msvcrt` file_lock 路径
   - 可能的编码问题（UTF-8 BOM）

**验收**: Windows CI 通过

**注意**: 可能需要修复一些 Windows 特定的测试失败。记录在执行记录中。

**执行记录**:
```
（由执行 Agent 填写）
```

---

### Phase 4 完成验收

```bash
# 本地验证
python -m pytest tests/ -v --timeout=300

# CI 验证（推送后检查 GitHub Actions）
# 1. bandit 扫描通过
# 2. Windows 测试通过
# 3. 现有 Ubuntu 测试不受影响
```

---

## Phase 5: 收尾 [FIX-19, FIX-20, FIX-21] — P3

### Batch 5A: 性能基准测试 [FIX-20]

#### Task 5A-1: 添加 pytest-benchmark 搜索性能基准

**目标文件**: 新建 `tests/benchmark/test_search_benchmark.py`

**实现**:
1. `pyproject.toml` 添加 `pytest-benchmark` 到 dev 依赖
2. 基准覆盖：
   - `hierarchical_search()` L1/L2/L3 各层
   - RRF 融合性能
   - FTS 搜索性能
   - 向量搜索性能（如果可用）

**注意**: benchmark 不在 CI 中阻塞，仅作为回归检测参考。

**执行记录**:
```
（由执行 Agent 填写）
```

---

### Batch 5B: 代码异味清理 [FIX-21]

#### Task 5B-1: 清理 sys.path.insert

**目标文件**: `tools/lib/semantic_search.py` line 24

**实现**: 移除 `sys.path.insert(0, ...)`，确保模块通过标准 import 路径可达。

**执行记录**:
```
（由执行 Agent 填写）
```

---

#### Task 5B-2: 清理函数内重复 import

**目标文件**: `tools/lib/vector_index_simple.py` line 46 (`import hashlib` 在函数内)

**实现**: 移到模块顶部。

**执行记录**:
```
（由执行 Agent 填写）
```

---

#### Task 5B-3: 文件名安全检查

**目标文件**: `tools/lib/config.py` 的 `JOURNAL_FILENAME_PATTERN`

**实现**: 添加 project 名的文件名安全检查（过滤特殊字符）。

**执行记录**:
```
（由执行 Agent 填写）
```

---

### Batch 5C: SKILL.md 精简 [FIX-19]

> **注意**: 用户明确表示"SKILL.md 最好也不要修改"。此 batch 标记为 **DEFER**，除非用户后续明确要求。

#### Task 5C-1: [DEFERRED] SKILL.md 精简至 ≤ 250 行

**状态**: 🟡 DEFERRED — 用户明确表示暂不修改 SKILL.md

**执行记录**:
```
DEFERRED: 用户指令 — "SKILL.md最好也不要修改，因为SKILL.md不影响on-boarding process"
```

---

### Phase 5 完成验收

```bash
python -m pytest tests/ -v --timeout=300
mypy tools/ --ignore-missing-imports
flake8 tools/ --count --max-complexity=40 --max-line-length=100

# 所有 Phase 完成后的最终验收：
# 1. 全量测试通过
# 2. 类型检查通过
# 3. 代码风格检查通过
# 4. contract tests 全部通过
# 5. web/services/write.py < 100 行
# 6. hierarchical_search() ≤ 100 行
# 7. 所有 lib/ 文件 ≤ 300 行
# 8. CI bandit + Windows 通过
```

---

## 附录 A: 文件变更预期总表

| 文件 | Phase | 变更类型 | 预期变化 |
|------|-------|----------|----------|
| `tools/write_journal/prepare.py` | 1A | 新建 | ~120 行 |
| `tools/write_journal/llm_extract.py` | 1A | 新建 | ~200 行 |
| `tools/write_journal/weather.py` | 1A | 修改 | +30 行（坐标支持） |
| `tools/write_journal/core.py` | 1A | 修改 | +20 行（enrich 参数） |
| `web/services/write.py` | 1B | 重写 | 341→~80 行 |
| `web/services/edit.py` | 1B | 重写 | 154→~40 行 |
| `web/services/llm_provider.py` | 1B | 删除/瘦身 | 650→~50 或删除 |
| `tools/edit_journal/diff.py` | 1B | 新建 | ~80 行 |
| `tests/contract/test_web_cli_alignment.py` | 1C | 扩展 | +6 个测试 |
| `tools/lib/search_constants.py` | 2A | 新建 | ~80 行 |
| `tools/search_journals/core.py` | 2A-2B | 重构 | 512→~100 行 |
| `tools/search_journals/ranking.py` | 2A | 修改 | 常量引用替换 |
| `tools/search_journals/keyword_pipeline.py` | 2B | 新建 | ~160 行 |
| `tools/lib/paths.py` | 3A | 新建 | ~180 行 |
| `tools/lib/search_config.py` | 3A | 新建 | ~100 行 |
| `tools/lib/config.py` | 3A | 瘦身 | 521→~250 行 |
| `tools/lib/attachment.py` | 3B | 新建 | ~90 行 |
| `tools/lib/schema.py` | 3B | 新建 | ~100 行 |
| `tools/lib/frontmatter.py` | 3B | 瘦身 | 488→~250 行 |
| `tools/lib/fts_search.py` | 3C | 新建 | ~150 行 |
| `tools/lib/fts_update.py` | 3C | 新建 | ~140 行 |
| `tools/lib/search_index.py` | 3C | 瘦身 | 459→~150 行 |
| `.github/workflows/ci.yml` | 4 | 修改 | +bandit, +windows |

---

## 附录 B: 风险与降级策略

| 风险 | 影响 | 降级策略 |
|------|------|----------|
| LLM 提取迁移到 CLI 后，Web 实时预览不可用 | 用户体验降级 | 添加 `/api/write/prepare` 端点调用 CLI extract |
| 搜索重构引入回归 | 搜索结果质量下降 | 每步之后跑 integration tests；保留旧函数作为 fallback 直到新版本验证 |
| 模块拆分破坏现有 import | 大范围报错 | re-export 保持兼容；逐步迁移 import 路径 |
| Windows CI 暴露大量平台特定 bug | CI 红灯阻塞 | 先用 `continue-on-error: true`，逐步修复 |
| pytest-benchmark 在不同机器上结果不稳定 | 误报性能回归 | 仅作为参考，不设硬阈值阻塞 |

---

## 附录 C: 执行检查清单（每个 Phase 完成后）

- [ ] 全量测试通过 (`python -m pytest tests/ -v`)
- [ ] 类型检查通过 (`mypy tools/ --ignore-missing-imports`)
- [ ] 代码风格通过 (`flake8 tools/` + `black --check tools/`)
- [ ] Contract tests 通过 (`python -m pytest tests/contract/ -v`)
- [ ] 所有变更文件的 import 无报错
- [ ] 更新 `CTO_AUDIT_REPORT.md` §7 对应 FIX 项的状态（🔴→🟢）
- [ ] Git commit（一个 Phase 一个 commit，message 说明完成了哪些 FIX）

---

> **文档结束**
>
> 本文档与 `CTO_AUDIT_REPORT.md` 共同构成 v1.5.5 改进的 authority anchor。
> 完成所有 Phase 后，两份文档一起归档至 `docs/archive/review-2026-03/`。
