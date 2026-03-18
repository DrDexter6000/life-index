# Retrieval Eval Cases

> **Document role**: Evaluation corpus for validating retrieval quality expectations across exact, fuzzy, semantic, and hybrid/fusion search behaviors
> **Audience**: Reviewers, implementers, and future agents working from the review bundle in `docs/review/`
> **Authority**: Review-scoped evaluation artifact; does not redefine runtime SSOT
> **Related artifacts**: `docs/review/execution/CANONICAL_WORKFLOWS.md`, `docs/review/execution/TOOL_RESPONSIBILITY_MATRIX.md`, `docs/review/execution/INDEX_CONSISTENCY_POLICY.md`

---

## 1. Purpose

These eval cases are designed to answer a different question from workflow evals.

Workflow eval asks:

- Did the system choose the right workflow and orchestrate it correctly?

Retrieval eval asks:

- Given a search request, does the retrieval system surface the right journal(s) with the right type of matching behavior?

This file does not require a specific ranking implementation. It defines the expected retrieval intent and the kind of result quality that should be observed.

---

## 2. Evaluation format

Each case includes:

- **Case ID**
- **Query style**
- **Representative user query**
- **Expected retrieval mode**
- **Expected target type**
- **Expected pass condition**

The “target type” is used here instead of a real journal filename because this review bundle is defining the evaluation structure before binding it to a concrete dataset.

---

## 3. Retrieval modes used in this file

### A. Exact

The query should succeed primarily because the journal contains the exact term, token, name, or phrase.

### B. Fuzzy

The query should succeed even when wording is close-but-not-identical, partially matching, or expressed through approximate filters.

### C. Semantic

The query should succeed because the journal is conceptually related, even if the exact wording is absent or sparse.

### D. Fusion

The query should benefit from combining multiple retrieval signals rather than relying on only one mode.

---

## 4. Eval cases

## Case RT-01 — Exact person-name retrieval

### Query style

- Exact

### Representative user query

“帮我找所有提到‘乐乐’的日志。”

### Expected retrieval mode

- Exact match should be sufficient

### Expected target type

- Entries explicitly mentioning 乐乐 in content, metadata, or indexed fields

### Expected pass condition

- Relevant entries are surfaced without requiring semantic inference to rescue the result

---

## Case RT-02 — Exact location retrieval

### Query style

- Exact

### Representative user query

“找一下所有写 Abuja 的日志。”

### Expected retrieval mode

- Exact / structured retrieval should be sufficient

### Expected target type

- Entries whose location field or content explicitly includes Abuja

### Expected pass condition

- Results reflect exact location mentions rather than conceptually nearby travel entries only

---

## Case RT-03 — Exact topic retrieval

### Query style

- Exact

### Representative user query

“帮我找所有 work 主题的日志。”

### Expected retrieval mode

- Exact metadata / filter-based retrieval

### Expected target type

- Entries with topic including `work`

### Expected pass condition

- Structured topic matches are returned reliably

---

## Case RT-04 — Exact date-bound retrieval

### Query style

- Exact

### Representative user query

“找 2026 年 3 月 7 日那天的日志。”

### Expected retrieval mode

- Exact date filtering should dominate

### Expected target type

- Entries from the requested date or date bucket

### Expected pass condition

- Retrieval respects exact date targeting rather than drifting into nearby days because of semantic similarity

---

## Case RT-05 — Fuzzy phrase variation

### Query style

- Fuzzy

### Representative user query

“找那种写到和朋友聚餐、吃饭聊天的日志。”

### Expected retrieval mode

- Fuzzy lexical retrieval should help, even if exact wording differs across entries

### Expected target type

- Entries about meals/social conversations with friends, even if they use slightly different wording

### Expected pass condition

- Relevant entries are not missed just because the exact phrase “聚餐” or “吃饭聊天” is absent

---

## Case RT-06 — Fuzzy nickname / variant wording

### Query style

- Fuzzy

### Representative user query

“找写到和女儿视频、通话、聊天的记录。”

### Expected retrieval mode

- Fuzzy matching should help bridge slightly different surface forms

### Expected target type

- Entries about contacting daughter, even if the wording varies between 视频 / 通话 / 聊天 / 打电话

### Expected pass condition

- Relevant family-contact entries cluster near the top despite wording variation

---

## Case RT-07 — Fuzzy emotional wording

### Query style

- Fuzzy

### Representative user query

“找那种有点紧张又兴奋的日志。”

### Expected retrieval mode

- Fuzzy matching plus metadata/helpful ranking cues

### Expected target type

- Entries whose mood/emotional wording is close to tension + excitement, even if exact adjectives differ

### Expected pass condition

- Entries with near-synonymous emotional descriptions remain retrievable

---

## Case RT-08 — Semantic concept retrieval: homesickness

### Query style

- Semantic

### Representative user query

“帮我找那种很想家、但没有直接说‘想家’的记录。”

### Expected retrieval mode

- Semantic retrieval should contribute materially

### Expected target type

- Entries expressing homesickness, longing, distance, or emotional displacement without exact “想家” wording

### Expected pass condition

- The system surfaces conceptually aligned entries that exact-only retrieval would likely miss

---

## Case RT-09 — Semantic concept retrieval: missing daughter

### Query style

- Semantic

### Representative user query

“找我那种想念女儿、但没有直说‘想她’的日志。”

### Expected retrieval mode

- Semantic retrieval should contribute materially

### Expected target type

- Entries whose emotional content reflects longing for daughter, even without explicit direct phrasing

### Expected pass condition

- Conceptually relevant family/emotion entries are surfaced despite wording gaps

---

## Case RT-10 — Semantic concept retrieval: career anxiety

### Query style

- Semantic

### Representative user query

“找那种对未来工作方向不太确定的记录。”

### Expected retrieval mode

- Semantic retrieval should contribute materially

### Expected target type

- Entries about professional uncertainty, product direction anxiety, or career drift even when they use different surface vocabulary

### Expected pass condition

- Retrieval captures the concept of uncertainty rather than only exact keywords like “焦虑” or “方向”

---

## Case RT-11 — Fusion query: structured + conceptual

### Query style

- Fusion

### Representative user query

“找 Abuja 那边、而且整体情绪比较平和的日志。”

### Expected retrieval mode

- Fusion of structured constraints and softer semantic/emotional relevance

### Expected target type

- Abuja-related entries whose emotional content is calm/settled/peaceful

### Expected pass condition

- Retrieval uses both location grounding and semantic tone rather than overfitting to only one of them

---

## Case RT-12 — Fusion query: exact person + semantic relationship tone

### Query style

- Fusion

### Representative user query

“找提到乐乐、而且整体有点心疼或牵挂情绪的日志。”

### Expected retrieval mode

- Exact mention plus semantic emotion signal

### Expected target type

- Entries explicitly mentioning 乐乐 and carrying the emotional tone of worry, tenderness, or longing

### Expected pass condition

- Exact-name filtering alone is not enough; semantic tone should improve ranking quality among multiple exact matches

---

## Case RT-13 — Fusion query: date scope + concept

### Query style

- Fusion

### Representative user query

“找最近这一个月里，那种状态明显变稳定了的记录。”

### Expected retrieval mode

- Date scoping plus semantic trend-oriented retrieval

### Expected target type

- Recent entries expressing increased stability, calmness, or restored order

### Expected pass condition

- Retrieval respects the requested time window while still surfacing semantically aligned emotional-state entries

---

## Case RT-14 — Negative-space retrieval / no useful result

### Query style

- Exact or semantic attempt, expected to fail cleanly

### Representative user query

“找一下我写过的关于冰岛极光的日志。”

### Expected retrieval mode

- Any mode may attempt retrieval, but likely no useful target exists

### Expected target type

- None, if the corpus truly lacks such entries

### Expected pass condition

- The system distinguishes empty or low-value retrieval from retrieval failure

---

## Case RT-15 — Source truth vs index lag check

### Query style

- Diagnostic retrieval

### Representative user query

“我刚手动改过一篇日志，现在帮我确认搜索还能不能找到。”

### Expected retrieval mode

- Search/diagnostic retrieval with awareness that index lag may exist

### Expected target type

- The relevant entry if indexes are current; otherwise a recognized visibility problem rather than false absence claim

### Expected pass condition

- The evaluation preserves the distinction between source truth and retrieval visibility, consistent with index policy

---

## Case RT-16 — Metadata-rich retrieval by tags/mood combination

### Query style

- Fusion / structured + fuzzy

### Representative user query

“找那些既和重构有关、又让我觉得有成就感的日志。”

### Expected retrieval mode

- Metadata/filter cues plus soft semantic ranking

### Expected target type

- Entries associated with refactoring / engineering cleanup plus positive accomplishment tone

### Expected pass condition

- Relevant entries rank above generic coding logs that mention refactor without the success/accomplishment dimension

---

## 5. Coverage summary

This file currently provides **16 retrieval eval cases**, which is above the roadmap minimum of 15.

Coverage includes:

- exact retrieval
- fuzzy lexical retrieval
- semantic retrieval
- hybrid/fusion retrieval
- empty-result handling
- source-truth vs retrieval-visibility distinction

---

## 6. Review criteria

This retrieval eval corpus is useful only if a reviewer can use it to ask:

- Is this query expected to succeed via exact, fuzzy, semantic, or fusion behavior?
- What kind of journal should be surfaced?
- Would exact-only retrieval likely fail where semantic retrieval should help?
- Is the system distinguishing retrieval weakness from retrieval failure?
- Is the system preserving the difference between journal existence and search visibility?
