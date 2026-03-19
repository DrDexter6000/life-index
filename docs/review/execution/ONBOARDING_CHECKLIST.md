# Onboarding Checklist

> **Document role**: Define the complete first-time user journey from installation to first successful search
> **Audience**: New users, Agent assistants, support documentation
> **Authority**: Review-scoped execution document; points to Tier 1 SSOT for command syntax
> **Primary goal**: Ensure every new user can verify their setup and complete their first write/search cycle

---

## 1. Overview

This checklist covers the complete onboarding flow:

```
Install → Initialize → Health Check → First Write → First Search
```

This ordering is intentional:

- `index` is the practical initialization step for a fresh install
- `health` is most useful **after** initialization, because a pre-init run may correctly report a degraded state when the data directory and indexes do not exist yet
- `write` and `search` are the final proof that the cold-start path actually works end to end

Each stage has:
- Required actions
- Expected outputs
- Common friction points
- Recovery steps

---

## 2. Stage 1: Install

### Prerequisites

| Requirement | Verification |
|:---|:---|
| Python 3.11+ | `python3 --version` or `python --version` |
| Git | `git --version` |
| ~200MB disk space | For code, venv, and embedding model |

### Installation steps

```bash
# 1. Clone repository
git clone --depth 1 https://github.com/DrDexter6000/life-index.git
cd life-index

# 2. Create virtual environment
python3 -m venv .venv

# 3. Install in editable mode
# Linux/macOS:
.venv/bin/pip install -e .

# Windows:
.venv\Scripts\pip install -e .
```

### Success criteria

- [ ] Repository cloned without errors
- [ ] Virtual environment created at `.venv/`
- [ ] Package installed with dependencies

### Friction point: Windows path confusion

**Symptom**: User tries to run `.venv/bin/life-index` on Windows and gets "command not found"

**Resolution**: Use `.venv\Scripts\life-index` (backslash, not forward slash; `Scripts`, not `bin`)

**Documentation reference**: `SKILL.md` "跨平台 venv 路径规则"

---

## 3. Stage 2: Initialize

### Build search index

```bash
# Linux/macOS:
.venv/bin/life-index index

# Windows:
.venv\Scripts\life-index index
```

### What happens

1. Creates `~/Documents/Life-Index/` directory structure
2. Downloads ~80MB embedding model (first run only, takes 1-3 minutes)
3. Initializes FTS5 and vector indexes

### Success criteria

- [ ] Command completes without errors
- [ ] Model download progress shown
- [ ] Index directory created at `~/Documents/Life-Index/.index/`

### Friction point: First index build takes time

**Symptom**: Command appears to hang during "Downloading embedding model..."

**Resolution**: This is expected. The model is ~80MB. Wait 1-3 minutes depending on connection speed. Do not interrupt.

**Documentation reference**: `README.md` "初始化搜索索引" section

---

## 4. Stage 3: Health Check

### Run health check

```bash
# Linux/macOS:
.venv/bin/life-index health

# Windows:
.venv\Scripts\life-index health
```

### Expected output structure

```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "python_version": "3.11.x",
    "venv_active": true,
    "checks": [
      {"name": "python_version", "status": "ok", ...},
      {"name": "virtual_env", "status": "ok", ...},
      {"name": "pyyaml", "status": "ok", ...},
      {"name": "fastembed", "status": "ok", ...},
      {"name": "data_directory", "status": "ok", ...},
      {"name": "search_index", "status": "ok", ...},
      {"name": "embedding_model", "status": "ok", ...}
    ],
    "issues": [],
    "issue_count": 0
  }
}
```

### Success criteria

- [ ] `success: true`
- [ ] `status` is "healthy" or "degraded" (not "unhealthy")
- [ ] No critical errors in `issues` array

### Fresh-install expectation

If `health` is run **before** Stage 2 initialization, a fresh install may legitimately return:

- `status: "degraded"`
- `data_directory.exists: false`
- `search_index.fts_index_exists: false`

That is not a failure by itself. The acceptance check for this onboarding path is the **post-init** health run.

### Acceptable warnings

| Warning | Meaning | Action |
|:---|:---|:---|
| `virtual_env: "warning"` | Not in venv | Expected if running via full path; acceptable |
| `fastembed: "warning"` | Semantic search unavailable | Optional; search will work without semantic features |
| `data_directory: "info"` | No journals yet | Expected on fresh install |

### Friction point: ModuleNotFoundError

**Symptom**: `ModuleNotFoundError: No module named 'fastembed'` or similar

**Resolution**:
1. Ensure you are using the venv Python: `.venv/bin/python` not system `python`
2. Re-run install: `.venv/bin/pip install -e .`
3. If venv is corrupted, delete `.venv/` and recreate

**Documentation reference**: `SKILL.md` "故障恢复" section

---

## 5. Stage 4: First Write

### Write first journal entry

```bash
# Linux/macOS:
.venv/bin/life-index write --data '{
  "title": "First Journal Entry",
  "content": "Today I set up Life Index. Looking forward to recording my journey.",
  "date": "2026-03-18",
  "topic": ["life"],
  "abstract": "Initial setup of Life Index journaling system.",
  "mood": ["hopeful"],
  "tags": ["setup"],
  "people": [],
  "project": "",
  "links": []
}'

# Windows (PowerShell):
.venv\Scripts\life-index write --data '{\n  "title": "First Journal Entry",\n  "content": "Today I set up Life Index. Looking forward to recording my journey.",\n  "date": "2026-03-18",\n  "topic": ["life"],\n  "abstract": "Initial setup of Life Index journaling system.",\n  "mood": ["hopeful"],\n  "tags": ["setup"],\n  "people": [],\n  "project": "",\n  "links": []\n}'
```

### Safer Windows variant (recommended)

The CLI supports `@file.json` input. On Windows this is usually more reliable than inline JSON:

```powershell
@'
{
  "title": "First Journal Entry",
  "content": "Today I set up Life Index. Looking forward to recording my journey.",
  "date": "2026-03-18",
  "topic": ["life"],
  "abstract": "Initial setup of Life Index journaling system.",
  "mood": ["hopeful"],
  "tags": ["setup"],
  "people": [],
  "project": "",
  "links": []
}
'@ | Out-File -FilePath first-entry.json -Encoding utf8

.venv\Scripts\life-index write --data @first-entry.json
```

### Expected output structure

```json
{
  "success": true,
  "data": {
    "journal_path": "Journals/2026/03/life-index_2026-03-18_001.md",
    "updated_indices": [...],
    "location_used": "Chongqing, China",
    "weather_used": "Sunny 25°C",
    "needs_confirmation": true,
    "confirmation_message": "日志已保存。地点：Chongqing, China；天气：Sunny 25°C。请确认以上信息是否正确？"
  }
}
```

### Success criteria

- [ ] `success: true`
- [ ] `journal_path` returned with valid path
- [ ] File exists at `~/Documents/Life-Index/Journals/2026/03/life-index_2026-03-18_001.md`

### Friction point: JSON escaping on Windows

**Symptom**: Command fails with JSON parse error on Windows

**Resolution**: Prefer `@file.json` input. If using inline JSON, use single quotes around the entire `--data` argument. In PowerShell, escaping is fragile, so file-based input is the safer default:

```powershell
# Alternative: write to file first
$json = @'
{
  "title": "First Journal Entry",
  ...
}
'@
$json | Out-File -FilePath "temp.json" -Encoding utf8
.venv\Scripts\life-index write --data (Get-Content "temp.json" -Raw)
```

### Friction point: Missing required fields

**Symptom**: Error about missing `abstract`, `topic`, or `mood`

**Resolution**: Include all required fields. See `docs/API.md` "write_journal" section for complete parameter list.

---

## 6. Stage 5: First Search

### Search for the entry just written

```bash
# Linux/macOS:
.venv/bin/life-index search --query "First Journal"

# Windows:
.venv\Scripts\life-index search --query "First Journal"
```

### Expected output structure

```json
{
  "success": true,
  "data": {
    "query": "First Journal",
    "total": 1,
    "results": [
      {
        "path": "Journals/2026/03/life-index_2026-03-18_001.md",
        "title": "First Journal Entry",
        "date": "2026-03-18",
        "abstract": "Initial setup of Life Index journaling system.",
        "score": 0.95
      }
    ],
    "search_time_ms": 45
  }
}
```

### Success criteria

- [ ] `success: true`
- [ ] `total` >= 1
- [ ] The entry just written appears in results

### Friction point: No results on first search

**Symptom**: `total: 0` even though journal was just written

**Resolution**:
1. Check that index was built: `.venv/bin/life-index index`
2. Try broader query: `--query "setup"`
3. Check journal file exists: `ls ~/Documents/Life-Index/Journals/2026/03/`

---

## 7. Fresh Install Rehearsal Log

This section documents a verified fresh installation to establish baseline expectations and identify friction points.

### Environment

| Attribute | Value |
|:---|:---|
| Date | 2026-03-18 |
| OS | Windows 11 |
| Python | 3.12.10 |
| Install mode | Fresh venv: `.venv-phase3` |
| Data directory | Isolated via `LIFE_INDEX_DATA_DIR` |

### Rehearsal steps executed

| Step | Command | Result | Time |
|:---|:---|:---|:---|
| 1. Create venv | `python -m venv .venv-phase3` | Success | completed |
| 2. Install | `.venv-phase3\Scripts\pip install -e .` | Success | completed |
| 3. Health check (pre-init) | `.venv-phase3\Scripts\life-index health` | Degraded by design | 1.33s |
| 4. Build index | `.venv-phase3\Scripts\life-index index` | Success | 7.34s |
| 5. Health check (post-init) | `.venv-phase3\Scripts\life-index health` | Healthy | verified |
| 6. First write | `life-index write --data ...` | Success | 6.01s |
| 7. First search | `life-index search --query "Phase 3 onboarding"` | Success | 3.77s |

**Total measured command time after install**: ~18.45s in the rehearsal environment.

Note: this run reused an already downloaded embedding model cache. A truly cold machine may still spend additional time downloading the model on first index build.

### Friction points observed

| # | Friction | Severity | Mitigation |
|:---|:---|:---|:---|
| 1 | Windows path syntax different from Unix | Medium | Document both variants prominently |
| 2 | Windows console encoding can break Unicode-rich JSON output | High | Fixed in this Phase 3 pass for `write` and `search` CLI output |
| 3 | `health` originally ignored `LIFE_INDEX_DATA_DIR` during rehearsal | Medium | Fixed in this Phase 3 pass; health now follows configured data dir |
| 4 | First index build may still require model download on a truly cold machine | Low | Document expected wait time |
| 5 | JSON escaping is tricky on Windows PowerShell | Medium | Recommend `--data @file.json` |
| 6 | Required fields are not obvious from CLI help alone | Low | Point to `docs/API.md` for full schema |
| 7 | Weather description may contain mojibake from upstream data in some environments | Low | Non-blocking; treat as separate output-quality issue if it persists |
| 8 | Default location "Chongqing, China" is author-specific | Medium | Agent must ask for location BEFORE first write; see SKILL.md "地点询问时机" |
| 9 | fastembed "mean pooling" warning on first run | Low | Non-blocking; cosmetic warning from library, does not affect functionality |

---

## 8. Quick Reference Card

### Commands by platform

| Action | Linux/macOS | Windows |
|:---|:---|:---|
| Health check | `.venv/bin/life-index health` | `.venv\Scripts\life-index health` |
| Build index | `.venv/bin/life-index index` | `.venv\Scripts\life-index index` |
| Write journal | `.venv/bin/life-index write --data '{...}'` | `.venv\Scripts\life-index write --data '{...}'` |
| Search | `.venv/bin/life-index search --query "..."` | `.venv\Scripts\life-index search --query "..."` |

### Data locations

| Location | Path |
|:---|:---|
| Journals | `~/Documents/Life-Index/Journals/` |
| Attachments | `~/Documents/Life-Index/attachments/` |
| Index | `~/Documents/Life-Index/.index/` |
| Config (optional) | `~/Documents/Life-Index/.life-index/config.yaml` |

---

## 9. Troubleshooting Quick Links

| Symptom | Check |
|:---|:---|
| `command not found` | Using correct path? Windows: `Scripts`, not `bin` |
| `ModuleNotFoundError` | In venv? Reinstall: `pip install -e .` |
| Index build hangs | Normal for first run; wait for model download |
| No search results | Run `life-index index` to rebuild |
| JSON parse error | Check quotes; Windows may need escaping |

---

## 10. SSOT References

| Truth | Location |
|:---|:---|
| Complete parameter schema | `docs/API.md` |
| CLI command reference | `SKILL.md` "Quick CLI Reference" |
| Health check details | `tools/__main__.py` `health_check()` |
| Installation instructions | `README.md` "快速安装" |
| Topic definitions | `docs/API.md` "Topic 分类定义" |

---

## 11. Maintenance Note

This checklist should be updated when:
1. New installation friction points are discovered
2. Command syntax changes in Tier 1 docs
3. New platforms are supported
4. Installation flow is modified

Last verified: 2026-03-18
