# Phase 4b2: Write Template — Split Subplan

**Parent plan:** [`plan-phase4b-write-route-template.md`](plan-phase4b-write-route-template.md)  
**Owns:** Task 11b 中 `web/templates/write.html` 部分  
**Why this split exists:** 写入页面 UI 复杂度高，单独 review 更清晰。

**Shared contracts:** [`shared-contracts.md`](shared-contracts.md)

## Scope

- write form layout
- template selector UI
- placeholders for LLM-available / unavailable mode
- geolocation button
- file upload / URL input widgets

## Contracts You Must Preserve

See [`shared-contracts.md`](shared-contracts.md) for canonical definitions.

- form hidden field uses `csrf_token`
- template JS 不覆盖已有用户输入
- UI 文案与 design-spec 一致

## Verification

- template selector works
- AI/manual placeholders switch correctly
- submit form remains compatible with route contract

## Current implementation status

- ✅ write form layout 已实现
- ✅ template selector UI 已实现
- ✅ LLM available / unavailable helper 文案已实现
- ✅ geolocation button 已实现
- ✅ file upload / URL input widgets 已实现
- ✅ template JS 已保证不覆盖已有用户输入
- ✅ URL input 支持动态增加输入框
