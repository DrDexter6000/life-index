# Life Index Web GUI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Full Web GUI MVP — FastAPI + Jinja2 + HTMX/Alpine.js serving Dashboard, Search, Journal View, Write, Edit pages with LLM metadata extraction and 8 Dashboard components.

**Architecture:** Layer C convenience shell around existing `tools/` (Layer A SSOT). FastAPI server renders Jinja2 templates; HTMX provides partial page updates; Alpine.js handles client-side interactivity. Service Layer wraps `tools/` CLI calls into Web-friendly data structures. No database — all data via existing tools modules.

**Tech Stack:** FastAPI, Jinja2, HTMX, Alpine.js, Tailwind CSS (CDN), ECharts (CDN), httpx, python-multipart, markdown

**Spec Reference:** `docs/specs/2026-03-22-web-gui-design.md` (v1.4)

---

## Phase 1: Project Scaffold & Core Infrastructure

**Goal:** `life-index serve` starts a working FastAPI app rendering a basic template.

### Task 1: pyproject.toml — add `[web]` optional deps + package discovery

**Files:** Modify `pyproject.toml`

- [ ] **Step 1:** Add `[project.optional-dependencies.web]` with: fastapi>=0.110.0, uvicorn[standard]>=0.27.0, jinja2>=3.1.0, python-multipart>=0.0.9, markdown>=3.5.0, httpx>=0.27.0
- [ ] **Step 2:** Update `all = ["life-index[dev]"]` → `all = ["life-index[dev,web]"]`
- [ ] **Step 3:** Change `include = ["tools*"]` → `include = ["tools*", "web*"]` in setuptools packages find
- [ ] **Step 4:** Verify: `python -c "import tomllib; t=tomllib.load(open('pyproject.toml','rb')); print(t['project']['optional-dependencies']['web'])"`
- [ ] **Step 5:** Commit with: `git add pyproject.toml && git commit -m "chore: add [web] optional deps and include web* in package discovery"`

### Task 2: E07xx error codes in `lib/errors.py`

**Files:** Modify `tools/lib/errors.py`

- [ ] **Step 1:** Read errors.py: `grep -n "^E0" tools/lib/errors.py | tail -5` to find last code
- [ ] **Step 2:** Add E0700–E0707 constants to Error enum: WEB_GENERAL_ERROR, URL_DOWNLOAD_FAILED, URL_CONTENT_TYPE_REJECTED, LLM_PROVIDER_UNAVAILABLE, LLM_EXTRACTION_FAILED, GEOLOCATION_FAILED, NOMINATIM_UNAVAILABLE, WEB_DEPS_MISSING
- [ ] **Step 3:** Add E0700–E0707 entries to ERROR_MESSAGES dict with Chinese descriptions
- [ ] **Step 4:** Run `python -m mypy tools/lib/errors.py --no-error-summary` — no new errors
- [ ] **Step 5:** Commit with: `git add tools/lib/errors.py && git commit -m "chore: add E07xx error codes for Web GUI"`

### Task 3: `web/` directory structure + config

**Files:** Create `web/__init__.py`, `web/config.py`, `web/routes/__init__.py`, `web/services/__init__.py`

- [ ] **Step 1:** Create `web/__init__.py` with docstring: "Life Index Web GUI — Layer C convenience shell."
- [ ] **Step 2:** Create `web/config.py`:
  - DEFAULT_PORT=8765, DEFAULT_HOST="127.0.0.1"
  - DATA_DIR, JOURNALS_DIR, ATTACHMENTS_DIR paths using Path.home() / "Documents" / "Life-Index"
  - LLM_API_KEY/BASE_URL/MODEL from os.environ.get with defaults
  - MAX_URL_DOWNLOAD_MB=50, URL_DOWNLOAD_TIMEOUT_S=30, MAX_CONCURRENT_DOWNLOADS=3
  - ALLOWED_CONTENT_TYPES set of image/audio/video/pdf/zip/text MIME types
- [ ] **Step 3:** Create empty `web/routes/__init__.py` and `web/services/__init__.py` with docstrings
- [ ] **Step 4:** Commit with: `git add web/__init__.py web/config.py web/routes/__init__.py web/services/__init__.py && git commit -m "chore: scaffold web/ directory structure and config"`

### Task 4: `web/app.py` — FastAPI application factory

**Files:** Create `web/app.py`

- [ ] **Step 1:** Create `web/app.py`:
  - `create_app()` returns FastAPI app
  - `_TEMPLATE_DIR = Path(__file__).parent / "templates"`
  - `_templates = Jinja2Templates(directory=_TEMPLATE_DIR)`
  - `GET /` returns `_templates.TemplateResponse("dashboard.html", {"request": request})`
- [ ] **Step 2:** Verify: `python -c "from web.app import create_app; app = create_app(); print('app created OK')"`
- [ ] **Step 3:** Commit with: `git add web/app.py && git commit -m "chore: add web/app.py FastAPI factory with root route"`

### Task 5: `life-index serve` CLI command

**Files:** Modify `tools/__main__.py`, create `web/__main__.py`

- [ ] **Step 1:** Read `tools/__main__.py`: `grep -n "cmd_map" tools/__main__.py | head -3`
- [ ] **Step 2:** Find cmd_map dict, add `"serve": "web.__main__:serve_main"`
- [ ] **Step 3:** Create `web/__main__.py`:
  - Import check for fastapi/uvicorn with clear error message (E0707)
  - `serve_main()`: argparse with --port (default 8765), --host (default 127.0.0.1), --reload
  - Call `uvicorn.run(create_app(), host=args.host, port=args.port, reload=args.reload)`
- [ ] **Step 4:** Verify: `python -m tools.__main__ serve --help`
- [ ] **Step 5:** Commit with: `git add tools/__main__.py web/__main__.py && git commit -m "feat: add life-index serve CLI command with dependency check"`

### Task 6: Jinja2 base template + theme support

**Files:** Create `web/templates/base.html`, `web/templates/dashboard.html` (stub), modify `web/app.py`

- [ ] **Step 1:** Create `web/templates/base.html`:
  - Tailwind CDN script, Alpine.js CDN (defer), HTMX CDN
  - `data-theme="light"` on html element
  - CSS: `[data-theme="dark"]` and `[data-theme="light"]` vars for bg/text
  - Nav: links to / (Life Index), /search, /write; theme toggle button with `@click` Alpine.js
  - `{% block title %}{% endblock %}` and `{% block content %}{% endblock %}`
- [ ] **Step 2:** Create `web/templates/dashboard.html` (stub) extending base.html
- [ ] **Step 3:** Verify app starts: start server and `curl http://127.0.0.1:8765/` returns HTML
- [ ] **Step 4:** Commit with: `git add web/templates/base.html web/templates/dashboard.html && git commit -m "feat: add Jinja2 base template with theme toggle"`

---

## Phase 2: Dashboard & Stats Service

**Goal:** Dashboard at `GET /` renders all 8 components with real data.

### Task 7: `web/services/stats.py` — stats aggregation + streak calculation

**Files:** Create `web/services/stats.py`, `tests/web/test_services.py`

- [ ] **Step 1:** Write failing test in `tests/web/test_services.py`:
  - `calculate_streak([])` → 0
  - `calculate_streak(["2026-03-22"])` → 1
  - `calculate_streak(["2026-03-20","2026-03-21","2026-03-22"])` → 3
  - `calculate_streak(["2026-03-20","2026-03-21","2026-03-23"])` → 2 (gap breaks)
  - `calculate_streak` with unordered dates handled correctly
  - `DashboardStats()` defaults to all zeros
- [ ] **Step 2:** Run test → FAIL (module not found)
- [ ] **Step 3:** Create `web/services/stats.py`:
  - `DashboardStats` dataclass: total_journals, total_characters, streak_days, this_month_count, top_mood, top_topic, topic_counts, mood_counts, tag_counts, people_counts, on_this_day, heatmap_data
  - `calculate_streak(sorted_dates)`: deduplicate, sort desc, iterate computing consecutive day gaps
  - `get_dashboard_stats(cache_path)`: import MetadataCache from tools.lib, get_all_journals(), aggregate all stats, on_this_day query matching M-DD with today
- [ ] **Step 4:** Run tests → PASS
- [ ] **Step 5:** Commit with: `git add tests/web/test_services.py web/services/stats.py && git commit -m "feat(stats): add DashboardStats service with streak calculation and on-this-day query"`

### Task 8: Dashboard route — full 8-component template

**Files:** Create `web/routes/dashboard.py`, `tests/web/test_routes.py`, `web/templates/partials/stats_cards.html`, replace `web/templates/dashboard.html`, modify `web/app.py`

- [ ] **Step 1:** Write failing test in `tests/web/test_routes.py`: mock `get_dashboard_stats`, `TestClient(create_app()).get("/")` → 200 + "Life Index"
- [ ] **Step 2:** Run test → FAIL
- [ ] **Step 3:** Create `web/routes/dashboard.py`: APIRouter, `GET /` → call `get_dashboard_stats(cache_path)`, render dashboard.html with stats
- [ ] **Step 4:** Wire `dashboard.router` into `web/app.py`: `from web.routes import dashboard; app.include_router(dashboard.router)`
- [ ] **Step 5:** Create `web/templates/partials/stats_cards.html`: 4-card grid (total journals, streak days, this month count, total chars in k)
- [ ] **Step 6:** Replace `web/templates/dashboard.html` with full implementation:
  - Include stats_cards partial
  - ECharts calendar heatmap (writing heatmap)
  - On This Day carousel (Alpine.js carousel with left/right arrows, year label, title, abstract, mood tags; empty state with encouraging text + "写日志" button)
  - Streak milestone badge (7/30/100/365 days, CSS animation, localStorage dedup)
  - Mood stacked bar chart (ECharts, per week/month)
  - Topic pie/ring chart (ECharts)
  - Tag word cloud (ECharts or simple tag list fallback)
  - People relationship graph (ECharts graph, force-directed)
  - All degradation states per spec §5.1 component degradation table
- [ ] **Step 7:** Run tests → PASS
- [ ] **Step 8:** Commit with: `git add web/routes/dashboard.py tests/web/test_routes.py web/templates/partials/stats_cards.html web/templates/dashboard.html && git commit -m "feat(dashboard): full 8-component dashboard with stats service"`

---

## Phase 3: Journal View & Search

### Task 9: Journal view route `GET /journal/{path:path}`

**Files:** Create `web/routes/journal.py`, `tests/web/test_journal_route.py`, `web/templates/journal.html`, modify `web/app.py`

- [ ] **Step 1:** Write failing test: create temp journal file, `TestClient.get("/journal/2026/03/test.md")` → 200 + content; `TestClient.get("/journal/../../etc/passwd")` → 400
- [ ] **Step 2:** Create `web/routes/journal.py`:
  - `GET /journal/{path:path}`: path traversal check `safe_path.resolve().startswith(JOURNALS_DIR.resolve())`, parse_frontmatter, markdown.markdown(body), render journal.html
  - `GET /attachments/{path:path}`: path traversal check, `FileResponse(safe_path)` from ATTACHMENTS_DIR
- [ ] **Step 3:** Create `web/templates/journal.html`: extends base.html, display frontmatter (title, date, location, weather, mood tags, tags), edit button linking to `/journal/{journal_path}/edit`, prose-styled markdown body
- [ ] **Step 4:** Wire into `web/app.py`
- [ ] **Step 5:** Run tests → PASS
- [ ] **Step 6:** Commit with: `git add web/routes/journal.py tests/web/test_journal_route.py web/templates/journal.html && git commit -m "feat(journal): add journal view route with path traversal protection"`

### Task 10: Search route `GET /search`

**Files:** Create `web/routes/search.py`, `web/services/search.py`, `tests/web/test_search_route.py`, `web/templates/search.html`, `web/templates/partials/search_results.html`

- [ ] **Step 1:** Write failing test: mock `search_journals` service, `TestClient.get("/search?q=test")` → 200
- [ ] **Step 2:** Create `web/services/search.py`: `search_journals(query, topic, date_from, date_to, level=3)` → call `python -m tools.search_journals --query ... --json`, parse JSON stdout, return dict
- [ ] **Step 3:** Create `web/routes/search.py`: `GET /search` with Query params (q, topic, date_from, date_to), call service, render search.html
- [ ] **Step 4:** Create `web/templates/search.html`: search form with q input, topic dropdown, date_from/date_to inputs, HTMX `hx-target="#results" hx-get="/search"` on form
- [ ] **Step 5:** Create `web/templates/partials/search_results.html`: iterate results, show title/date/mood/abstract snippet, link to journal
- [ ] **Step 6:** Wire into `web/app.py`
- [ ] **Step 7:** Run tests → PASS
- [ ] **Step 8:** Commit with: `git add web/routes/search.py web/services/search.py tests/web/test_search_route.py web/templates/search.html web/templates/partials/search_results.html && git commit -m "feat(search): add search route with HTMX partial updates"`

---

## Phase 4: Write & Edit Pages + LLM Integration

### Task 11: Write page + APIKeyProvider

**Files:** Create `web/routes/write.py`, `web/services/journal.py`, `web/services/llm_provider.py`, `tests/web/test_write_route.py`, `web/templates/write.html`, `web/templates/writing_templates.json`, modify `web/app.py`

- [ ] **Step 1:** Write failing test: `GET /write` → 200; `POST /write` with empty data → 400/422
- [ ] **Step 2:** Create `web/services/llm_provider.py`:
  - `LLMProvider` ABC: `extract_metadata(content)` and `is_available()`
  - `APIKeyProvider`: reads LLM_API_KEY/BASE_URL/MODEL from config; `is_available()` → bool(api_key); `extract_metadata()` → async httpx POST to /chat/completions with structured Chinese prompt asking for JSON metadata
  - `HostAgentProvider`: `is_available()` → False (MVP placeholder); `extract_metadata()` → {}
  - `get_provider()`: try HostAgentProvider first, fallback to APIKeyProvider, return None if both unavailable
- [ ] **Step 3:** Create `web/services/journal.py`: `write_journal(data)` → call `python -m tools.write_journal --data JSON`
- [ ] **Step 4:** Create `web/routes/write.py`:
  - `GET /write`: load `writing_templates.json`, render write.html with templates list and llm_available flag
  - `POST /write`: collect form data (content, title, topic, mood, tags, people, location, attachments files+URLs), merge with LLM-extracted metadata for empty fields per spec §5.4.1 smart-fill priority, call write_journal, handle errors returning to form
- [ ] **Step 5:** Create `web/templates/write.html`: template selector dropdown (Alpine.js, switches content), all form fields per spec §5.4.1 table, location input with 📍 button (Geolocation API), file upload input, URL input, topic dropdown (7 options), mood/tags/people tag inputs, submit button with HTMX
- [ ] **Step 6:** Create `web/templates/writing_templates.json`: 7 presets (空白, 给团团的信, 今日感恩, 工作日志, 学习笔记, 读后感, 健康打卡) per spec §5.4.5
- [ ] **Step 7:** Wire into `web/app.py`
- [ ] **Step 8:** Run tests → PASS
- [ ] **Step 9:** Commit with: `git add web/routes/write.py web/services/journal.py web/services/llm_provider.py tests/web/test_write_route.py web/templates/write.html web/templates/writing_templates.json && git commit -m "feat(write): add write page with APIKeyProvider LLM integration and templates"`

### Task 12: Edit page + weather query integration

**Files:** Create `web/routes/edit.py`, `tests/web/test_edit_route.py`, `web/templates/edit.html`, extend `web/services/journal.py`

- [ ] **Step 1:** Write failing test: load existing journal, edit fields, assert updated
- [ ] **Step 2:** Extend `web/services/journal.py`: add `edit_journal(journal_path, **kwargs)` → call `python -m tools.edit_journal --journal ... --set-field value` for each kwarg
- [ ] **Step 3:** Create `web/routes/edit.py`:
  - `GET /journal/{path}/edit`: load frontmatter, render edit.html
  - `POST /journal/{path}/edit`: compute diff of changed fields, call edit_journal, on location change → trigger weather query (500ms debounce, show loading state), redirect to journal view on success
- [ ] **Step 4:** Create `web/templates/edit.html`: pre-filled form with all editable frontmatter fields, location blur → weather auto-fill (Alpine.js debounce), weather field as editable suggestion
- [ ] **Step 5:** Wire into `web/app.py`
- [ ] **Step 6:** Run tests → PASS
- [ ] **Step 7:** Commit with: `git add web/routes/edit.py tests/web/test_edit_route.py web/templates/edit.html && git commit -m "feat(edit): add edit page with location-weather coupling"`

---

## Phase 5: Polish, URL Downloads & Final Integration

### Task 13: URL remote download + CSRF protection

**Files:** Modify `web/routes/write.py`, create `tests/web/test_url_download.py`

- [ ] **Step 1:** Write failing test: mock httpx, assert URL download to attachments/YYYY/MM/
- [ ] **Step 2:** Add URL download logic to write route:
  - ALLOWED_CONTENT_TYPES validation per spec §5.4.3
  - 50MB size limit via Content-Length or streaming count
  - 30s timeout per download
  - Max 3 concurrent downloads (asyncio.Semaphore)
  - Download to `attachments/YYYY/MM/` preserving original filename, appending序号 on conflict
  - Return file path reference; failed URLs listed in response (don't block write)
- [ ] **Step 3:** Add CSRF token to write form: generate token in session, validate on POST
- [ ] **Step 4:** Run tests → PASS
- [ ] **Step 5:** Commit with: `git add web/routes/write.py tests/web/test_url_download.py && git commit -m "feat(write): add URL remote download with Content-Type validation and CSRF protection"`

### Task 14: E2E smoke test + CI integration

**Files:** Create `tests/web/test_integration.py`, modify CI workflow if needed

- [ ] **Step 1:** Write e2e test: start server in subprocess via `TestClient`, test write → view → search flow
- [ ] **Step 2:** Verify: `python -m pytest tests/web/ -v --cov=web --cov-fail-under=70`
- [ ] **Step 3:** Ensure CI runs web tests only when web/ files change (use path filter in workflow)
- [ ] **Step 4:** Commit with: `git add tests/web/test_integration.py && git commit -m "test(web): add e2e smoke test and CI integration"`
