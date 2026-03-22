# Life Index Web GUI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Full Web GUI MVP — FastAPI + Jinja2 + HTMX/Alpine.js serving Dashboard, Search, Journal View, Write, Edit pages with LLM metadata extraction and 8 Dashboard components.

**Architecture:** Layer C convenience shell around existing `tools/` (Layer A SSOT). FastAPI server renders Jinja2 templates; HTMX provides partial page updates; Alpine.js handles client-side interactivity. Service Layer wraps `tools/` modules into Web-friendly data structures. No database — all data via existing tools modules.

**Tech Stack:** FastAPI, Jinja2, HTMX, Alpine.js, Tailwind CSS (CDN), ECharts (CDN), httpx, python-multipart, markdown

**Spec Reference:** `docs/web-gui/design-spec.md` (v1.4)

---

## Phase 0: Prerequisites

Before starting any task, the following conditions **MUST** be satisfied:

### Environment

- [ ] Python 3.11+ installed: `python --version` → `Python 3.11.x` or `3.12.x`
- [ ] Repository cloned and on correct branch
- [ ] Editable install with dev deps: `pip install -e ".[dev]"` → exit code 0
- [ ] Existing tests pass: `python -m pytest tests/unit/ -q` → all pass, 0 failures

### Knowledge

- [ ] Read the design spec: `docs/web-gui/design-spec.md` (814 lines — full read required)
- [ ] Read existing error codes: `tools/lib/errors.py` (ErrorCode class, RECOVERY_STRATEGIES dict)
- [ ] Read CLI entry point: `tools/__main__.py` lines 286-294 (cmd_map dict)
- [ ] Read metadata cache API: `tools/lib/metadata_cache.py` function `get_all_cached_metadata()` at line 251
- [ ] Read test conventions: `tests/unit/test_config.py` (class TestXxx pattern)

### Codebase Conventions (MUST follow)

| Convention | Details |
|:--|:--|
| Naming | Functions/vars: `snake_case`; Constants: `UPPER_SNAKE_CASE`; Classes: `PascalCase` |
| Paths | Always `pathlib.Path`, never string concatenation |
| Encoding | All files UTF-8 |
| JSON output | 错误返回统一为 `{"success": false, "error": {...}}`；成功返回沿用各工具当前的顶层字段结构 |
| Error codes | `ErrorCode.XXX = "E0NNN"` with recovery strategy in `RECOVERY_STRATEGIES` |
| Tests | `class TestXxx:` with `def test_xxx(self):` methods |
| TDD cycle | Write failing test → run → RED → implement → run → GREEN → commit |
| Imports | Absolute imports: `from tools.lib.errors import ErrorCode` |

---

## Phase Navigation

This plan is split into phase files for manageable size. Execute in order — each phase depends on the previous.

| Phase | File | Tasks | Goal |
|:--|:--|:--|:--|
| **Phase 1** | [plan-phase1-scaffold.md](plan-phase1-scaffold.md) | Tasks 1–6 | `life-index serve` starts a working FastAPI app |
| **Phase 2** | [plan-phase2-dashboard.md](plan-phase2-dashboard.md) | Tasks 7–8 | Dashboard renders all 8 components with real data |
| **Phase 3** | [plan-phase3-journal-search.md](plan-phase3-journal-search.md) | Tasks 9–10 | Journal view + search with HTMX partial updates |
| **Phase 4a** | [plan-phase4a-llm-write-service.md](plan-phase4a-llm-write-service.md) | Task 11a | LLM Provider + Write Service backend + writing templates JSON |
| **Phase 4b** | [plan-phase4b-write-route-template.md](plan-phase4b-write-route-template.md) | Task 11b | Write route + write.html template with smart-fill UI |
| **Phase 4c** | [plan-phase4c-edit.md](plan-phase4c-edit.md) | Task 12 | Edit service + route + template with diff-based submission |
| **Phase 5** | [plan-phase5-polish.md](plan-phase5-polish.md) | Tasks 13–14 | URL downloads, CSRF, E2E smoke test |

### Split Subplans

- Phase 2a: [plan-phase2a-stats-service.md](plan-phase2a-stats-service.md)
- Phase 2b: [plan-phase2b-dashboard-route-template.md](plan-phase2b-dashboard-route-template.md)
- Phase 2 legacy full: [plan-phase2-dashboard-legacy-full.md](plan-phase2-dashboard-legacy-full.md)
- Phase 3a: [plan-phase3a-journal-view.md](plan-phase3a-journal-view.md)
- Phase 3b: [plan-phase3b-search.md](plan-phase3b-search.md)
- Phase 3 legacy full: [plan-phase3-journal-search-legacy-full.md](plan-phase3-journal-search-legacy-full.md)
- Phase 4a1: [plan-phase4a1-llm-provider.md](plan-phase4a1-llm-provider.md)
- Phase 4a2: [plan-phase4a2-write-service.md](plan-phase4a2-write-service.md)
- Phase 4a3: [plan-phase4a3-writing-templates.md](plan-phase4a3-writing-templates.md)
- Phase 4a legacy full: [plan-phase4a-llm-write-service-legacy-full.md](plan-phase4a-llm-write-service-legacy-full.md)
- Phase 4b1: [plan-phase4b1-write-route.md](plan-phase4b1-write-route.md)
- Phase 4b2: [plan-phase4b2-write-template.md](plan-phase4b2-write-template.md)
- Phase 4b legacy full: [plan-phase4b-write-route-template-legacy-full.md](plan-phase4b-write-route-template-legacy-full.md)
- Phase 4c1: [plan-phase4c1-edit-service.md](plan-phase4c1-edit-service.md)
- Phase 4c2: [plan-phase4c2-edit-route-template.md](plan-phase4c2-edit-route-template.md)
- Phase 4c legacy full: [plan-phase4c-edit-legacy-full.md](plan-phase4c-edit-legacy-full.md)

### Maintenance Note: These phase docs are still too large

实施前建议继续拆分以下 phase 文档，否则执行与 review 成本仍然过高：

- `plan-phase2-dashboard.md` → `stats-service`, `dashboard-route-template`, `charts`
- `plan-phase3-journal-search.md` → `journal-view`, `search`
- `plan-phase4a-llm-write-service.md` → `llm-provider`, `write-service`, `writing-templates`
- `plan-phase4b-write-route-template.md` → `write-route`, `write-template`
- `plan-phase4c-edit.md` → `edit-service`, `edit-route-template`

拆分时必须保持：

- task 编号稳定
- 依赖关系显式写出
- `journal_route_path` / CSRF / tool return shape 契约只在一个地方定义，其余文档引用

### Dependency Graph

```
Phase 1 (Tasks 1-6): Scaffold
    ├── Task 1: pyproject.toml
    ├── Task 2: E07xx error codes ── (independent of Task 1)
    ├── Task 3: web/ directory ──── (after Task 1)
    ├── Task 4: web/app.py ──────── (after Task 3)
    ├── Task 5: CLI serve command ─ (after Task 4)
    └── Task 6: base template ───── (after Task 4)

Phase 2 (Tasks 7-8): Dashboard
    ├── Task 7: stats service ───── (after Task 3)
    └── Task 8: dashboard route ─── (after Tasks 6 + 7)

Phase 3 (Tasks 9-10): Journal + Search
    ├── Task 9: journal view ────── (after Task 6)
    └── Task 10: search route ───── (after Task 6)

Phase 4a (Task 11a): LLM + Write Service
    └── Task 11a: LLM provider + write service + writing_templates.json ─ (after Task 6)

Phase 4b (Task 11b): Write Route + Template
    └── Task 11b: write route + write.html ─ (after Phase 4a)

Phase 4c (Task 12): Edit
    └── Task 12: edit service + route + template ─ (after Tasks 9 + Phase 4b)

Phase 5 (Tasks 13-14): Polish
    ├── Task 13: URL download ───── (after Phase 4b)
    └── Task 14: E2E smoke test ─── (after all above)
```

### Key API References

**`tools/lib/metadata_cache.get_all_cached_metadata(conn=None)`** — Returns `List[Dict]`:
```python
[{
    "file_path": "C:/Users/.../Documents/Life-Index/Journals/2026/03/life-index_2026-03-07_001.md",
    "date": "2026-03-07",           # date string (YYYY-MM-DD)
    "title": "日志标题",
    "location": "Lagos, Nigeria",
    "weather": "晴天 28°C",
    "topic": ["work", "create"],     # JSON-parsed list
    "project": "LifeIndex",
    "tags": ["重构", "优化"],         # JSON-parsed list
    "mood": ["专注", "充实"],         # JSON-parsed list
    "people": ["团团"],               # JSON-parsed list
    "abstract": "100字内摘要",
    "metadata": { ... }              # duplicate of above fields (nested dict)
}]
```

**`tools/lib/errors.ErrorCode`** — Add E07xx constants (Web Module):
```python
# ========== Web Module (07xx) ==========
WEB_GENERAL_ERROR = "E0700"        # recovery: ask_user
URL_DOWNLOAD_FAILED = "E0701"      # recovery: skip_optional
URL_CONTENT_TYPE_REJECTED = "E0702" # recovery: ask_user
LLM_PROVIDER_UNAVAILABLE = "E0703" # recovery: skip_optional
LLM_EXTRACTION_FAILED = "E0704"   # recovery: skip_optional
GEOLOCATION_FAILED = "E0705"      # recovery: skip_optional
NOMINATIM_UNAVAILABLE = "E0706"   # recovery: skip_optional
WEB_DEPS_MISSING = "E0707"        # recovery: fail
```

**`tools/__main__.py` cmd_map** (line 286):
```python
cmd_map = {
    "write": "tools.write_journal.__main__",
    "search": "tools.search_journals.__main__",
    # ... existing entries ...
    "serve": "web.__main__",  # NEW — must match module.__main__ pattern
}
```

**`tools/lib/frontmatter.parse_journal_file(path)`** — Returns dict with frontmatter fields + `"_body"` / `"_file"` helper keys.

### Web Path Normalization Rule

底层工具当前可能返回：

- 绝对路径（最常见）
- `Journals/...` 形式的 `USER_DATA_DIR` 相对路径

Web 层对外统一暴露：

- `journal_route_path = path relative to JOURNALS_DIR`
- 示例：`2026/03/life-index_2026-03-07_001.md`

所有模板链接、redirect、breadcrumb 都必须基于 `journal_route_path`，而不是直接使用底层 `path` / `file_path`。

**`tools/lib/config`** — Key constants: `USER_DATA_DIR`, `JOURNALS_DIR`, `ATTACHMENTS_DIR`.
