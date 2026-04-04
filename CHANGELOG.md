# Life Index Changelog

This changelog records user-visible milestones for the v1.x CLI line.

## [Unreleased]

- No unreleased user-facing changes recorded yet.

## [1.5.5] - 2026-03-29

### Fixed
- Stabilized CI on Windows by removing Unicode-sensitive console output and normalizing generated topic filenames.
- Reduced weather-related timeout flakiness in test and CI environments.
- Fixed several flaky search and timing assertions that could fail under mocked or fast execution paths.

### Improved
- Modernized Python 3.11+ typing across search and FTS modules.
- Added regression coverage for FTS logging and typing modernization.

## [1.5.0] - 2026-04-03

### What users get
- Life Index is now positioned as an **Agent-Native CLI journal system** with a cleaned release surface.
- Old Web GUI materials are preserved only as historical archive references, not as the active product path.

### Included in this release
- **Search quality upgrades**: stronger semantic retrieval, AND-first FTS behavior, and more reliable ranking thresholds.
- **Entity Graph**: alias-aware entity resolution, relationship modeling, query expansion, and entity maintenance CLI.
- **Write enhancements**: sentiment score, themes, entity extraction, revision history, and backfill tooling.
- **Tool schema standardization**: per-tool `schema.json` files and shared schema validation support.
- **Release cleanup**: README alignment, schedule consolidation, and CLI-only release orientation.

## [1.4.0] - 2026-03-28

### What users get
- All core CLI tools now expose standardized machine-readable tool schemas.
- Agents can integrate with the CLI more consistently because tool contracts are explicit instead of implicit.

## [1.3.0] - 2026-04-03

### What users get
- Journal writing now captures richer structure: `sentiment_score`, `themes`, `entities`, and revision history.
- Existing journals can be backfilled so older records benefit from the same metadata model.

## [1.2.0] - 2026-04-03

### What users get
- Searches can understand people, places, projects, and aliases instead of depending on exact wording.
- The new Entity Graph lets agents resolve names like family roles or nicknames into the right underlying entity.

## [1.1.0] - 2026-04-03

### What users get
- Search became more precise and less noisy through `bge-m3`, AND-first keyword behavior, and threshold tuning.
- Keyword and semantic retrieval now cooperate more reliably, improving recall without flooding the result set.

## [1.0.0] - 2026-03-04

### What users get
- First stable CLI release with local-first Markdown journaling, search, editing, weather lookup, indexing, abstracts, and backup.
- Established the core Life Index workflow: write through an agent, store locally forever, and retrieve later with structured search.
