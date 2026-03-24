# Web GUI Implementation Plan — Thin Index

**Goal:** Provide one clean entrypoint for the Web GUI documentation set without forcing readers through oversized planning documents.

## Recommended reading order

1. [design-spec.md](design-spec.md)
2. [shared-contracts.md](shared-contracts.md)
3. [design-spec.md §11 已知问题与实现注意事项](design-spec.md#11-已知问题与实现注意事项)
4. Phase index docs (below)
5. Split subplans for actual execution
6. Legacy full docs only when you need the original long-form TDD detail

## Phase indexes

- Phase 1: [plan-phase1-scaffold.md](plan-phase1-scaffold.md)
- Phase 2: [plan-phase2-dashboard.md](plan-phase2-dashboard.md)
- Phase 3: [plan-phase3-journal-search.md](plan-phase3-journal-search.md)
- Phase 4a: [plan-phase4a-llm-write-service.md](plan-phase4a-llm-write-service.md)
- Phase 4b: [plan-phase4b-write-route-template.md](plan-phase4b-write-route-template.md)
- Phase 4c: [plan-phase4c-edit.md](plan-phase4c-edit.md)
- Phase 5: [plan-phase5-polish.md](plan-phase5-polish.md)

## Split subplans

### Phase 2
- [plan-phase2a-stats-service.md](plan-phase2a-stats-service.md)
- [plan-phase2b-dashboard-route-template.md](plan-phase2b-dashboard-route-template.md)

### Phase 3
- [plan-phase3a-journal-view.md](plan-phase3a-journal-view.md)
- [plan-phase3b-search.md](plan-phase3b-search.md)

### Phase 4a
- [plan-phase4a1-llm-provider.md](plan-phase4a1-llm-provider.md)
- [plan-phase4a2-write-service.md](plan-phase4a2-write-service.md)
- [plan-phase4a3-writing-templates.md](plan-phase4a3-writing-templates.md)

### Phase 4b
- [plan-phase4b1-write-route.md](plan-phase4b1-write-route.md)
- [plan-phase4b2-write-template.md](plan-phase4b2-write-template.md)

### Phase 4c
- [plan-phase4c1-edit-service.md](plan-phase4c1-edit-service.md)
- [plan-phase4c2-edit-route-template.md](plan-phase4c2-edit-route-template.md)

## Shared contracts

All phase docs should defer to:

- [shared-contracts.md](shared-contracts.md)

This document is the single reference for:

- `journal_route_path`
- `csrf_token` contract
- `_body` usage from `parse_journal_file()`
- current tool return-shape expectations

## Legacy full docs

- [implementation-plan-legacy-full.md](implementation-plan-legacy-full.md)
- [plan-phase2-dashboard-legacy-full.md](plan-phase2-dashboard-legacy-full.md)
- [plan-phase3-journal-search-legacy-full.md](plan-phase3-journal-search-legacy-full.md)
- [plan-phase4a-llm-write-service-legacy-full.md](plan-phase4a-llm-write-service-legacy-full.md)
- [plan-phase4b-write-route-template-legacy-full.md](plan-phase4b-write-route-template-legacy-full.md)
- [plan-phase4c-edit-legacy-full.md](plan-phase4c-edit-legacy-full.md)

## Execution guidance

- Prefer thin phase index → split subplan flow
- Open legacy full docs only for missing step-by-step detail
- Do not redefine shared contracts in individual phase docs unless the contract itself is changing

## Current implementation snapshot

- ✅ Phase 1 scaffold 已完成
- ✅ Phase 2 dashboard 已完成
- ✅ Phase 3 journal view + search 已完成
- ✅ Phase 4a write foundations 已完成（LLM provider / write service / writing templates）
- ✅ Phase 4b write route + template 已完成，并已包含附件桥接与成功/失败 warning surfacing
- ✅ Phase 4c edit foundation 已完成，并已包含 `/api/weather` 与 location/weather 前端闭环
- ✅ Phase 5 closeout 已完成（独立 URL download service、CSRF/E2E 验证、release-readiness 收尾）

## Post-release snapshot (v1.4.0)

### Verified status

- 已执行最终 aggregated Web regression：scaffold / dashboard / journal / search / write / edit / url_download / csrf / e2e 全部通过
- Web GUI 已随 **v1.4.0** 正式发布（PR #3 已合并，tag / GitHub Release 已发布）
- 主链路（写入、附件桥接、warning surfacing、编辑、天气联动、独立 URL download service、CSRF contract、E2E smoke）均已跑通

### Remaining gaps

1. **部分产品 polish 仍未完成**
   - write / edit 仍可继续做更细的 geolocation / weather 联动 polish（目前已具备 reverse geocoding、自动天气填充、loading/status feedback）
2. **design-spec 与实现仍有少量 wording/strictness 差异**
   - 主要集中在 Phase 5 reject-list 细节描述与 residual polish wording
3. **剩余开放项已降级为 post-MVP polish，而非 release blocker**
   - 当前已具备 success-criteria checklist、readiness note、aggregated regression 证据
4. **下一阶段工作应转为 backlog 驱动，而非继续 release closeout**
   - 建议统一参考 `post-v1.4-backlog.md` 管理后续产品增强项与文档 closeout

### Next batch candidates

#### Batch F — Post-MVP product polish（下一批建议）

1. geolocation reverse geocoding
2. edit / write 交互进一步 polish
3. 更细粒度 attachment / weather UX 优化

> **Update (2026-03-22):** Batch F 的第 1 项（geolocation reverse geocoding）已完成：浏览器定位现在通过 `/api/reverse-geocode` 将坐标解析为人类可读地点字符串，并已接入 write / edit 页面，同时保留坐标字符串 fallback。

> **Update (2026-03-22, Batch G):** write / edit 页面现已补上 geolocation → auto weather fetch、按钮 busy/disabled 状态、以及 inline weather status 文案。

> **Update (2026-03-22, Batch H):** write / edit 表单现已补上 submit busy/status feedback；write 页附件区已补上本地文件选择状态、URL 输入状态与 URL remove affordance。剩余开放项已进一步收敛到更细粒度内容结构与移动端/视觉 polish。

> **Update (2026-03-22, Batch I):** dashboard / search / write / edit 已完成一轮 mobile/responsive 与 spacing consistency polish：标题、卡片 padding、按钮区与结果区在窄屏下的堆叠逻辑已统一，后续开放项进一步收敛到更细粒度的视觉 refinement 与信息密度优化。

> **Update (2026-03-22, Batch J):** 已完成一轮 template-only visual refinement：dashboard 卡片层次更统一，journal 页 metadata 信息层级更清晰，write/edit/search 的主要按钮达到更友好的触控尺寸。当前开放项已进一步收敛到非阻塞性的 aesthetic/detail polish。

> **Update (2026-03-22, Batch K):** 已完成 base layout/nav micro-polish 与一轮 wording consistency closeout：nav CTA、theme toggle、search CTA 与部分 helper/empty-state 文案已统一到更一致的触控与语言风格。当前已基本没有值得继续成批推进的主线 polish 项。

> **Update (2026-03-22, Post-walkthrough bugfix):** 真实 Playwright walkthrough 暴露的两处主链路缺陷已修复并回归验证通过：`/write` 对空 `attachments` 表单值的 422 问题已在 route 边界兼容；search results 对 `score=None` 的模板渲染 500 问题已修复。write → journal → edit → search → dashboard reload 的真实浏览器 walkthrough 已打通。

## Final release review summary

- **Release status:** Shipped in v1.4.0
- **Reason:** 主链路、专项测试、integration/E2E smoke、aggregated regression、真实 Playwright walkthrough、以及 GitHub release 链路均已具备
- **Remaining work type:** backlog 化的 post-MVP polish / feature expansion，而非当前交付阻塞项
- **Next planning anchor:** `docs/web-gui/post-v1.4-backlog.md`
