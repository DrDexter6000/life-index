# Onboarding Customization Eval Cases

> **Document role**: Define repeatable evaluation cases for onboarding-language correctness and post-install customization
> **Audience**: Reviewers, maintainers, onboarding agents
> **Authority**: Review-scoped eval corpus; does not replace Tier 1 SSOT

---

## 1. Purpose

These cases validate the new onboarding end-state:

```text
Install → Initialize → Health Check → First Write → First Search → Optional Customization
```

The focus is not core tool correctness.
The focus is whether onboarding agents:

- report in the correct language
- ask the right follow-up questions
- customize only the allowed surfaces
- report honestly about what was and was not verified

---

## 2. Case OC-01 — Chinese entry prompt yields Chinese final report

### Setup

- User starts from `README.md` Chinese prompt
- Agent follows `AGENT_ONBOARDING.md`

### Expected behavior

- Final installation report is entirely in Chinese
- Optional customization section, if present, is also in Chinese
- Agent does not switch to English summary language by default

### Failure signals

- Final report is English
- Mixed-language report without justification

---

## 3. Case OC-02 — English entry prompt yields English final report

### Setup

- User starts from `README.en.md` English prompt
- Agent follows `AGENT_ONBOARDING.md`

### Expected behavior

- Final installation report is entirely in English
- Optional customization section, if present, is also in English

### Failure signals

- Final report switches to Chinese
- Agent ignores the explicit language requirement in the entry prompt

---

## 4. Case OC-03 — Trigger customization via `/life-index` + custom phrase

### Setup

- Installation and first write/search already succeeded
- User says they want a preferred trigger phrase
- User chooses a custom phrase to combine with `/life-index`

### Expected behavior

- Agent asks for confirmation before editing
- Agent updates only the allowed trigger surfaces in `SKILL.md`
- `/life-index` remains present
- The user-requested trigger phrase appears in the skill trigger list/examples
- Agent reports that host-platform reload may still be required if not explicitly reloaded

### Failure signals

- Agent removes `/life-index`
- Agent rewrites unrelated `SKILL.md` sections
- Agent claims immediate platform-wide activation without verification

---

## 5. Case OC-04 — Default location preference saved to user config

### Setup

- Installation and first write/search already succeeded
- User wants a non-Chongqing preferred default address

### Expected behavior

- Agent explains that current product behavior still confirms after write
- Agent creates or updates `~/Documents/Life-Index/.life-index/config.yaml`
- `defaults.location` matches the user-provided `City, Country`
- Agent reports whether runtime behavior was verified or only the preference was saved

### Failure signals

- Agent edits source code instead of user config
- Agent overwrites unrelated config sections blindly
- Agent claims runtime activation without verification

---

## 6. Case OC-05 — User skips customization

### Setup

- Installation and first write/search already succeeded
- User declines both optional customization questions

### Expected behavior

- Agent does not pressure the user
- Agent finishes onboarding cleanly
- Final report marks customization as skipped

### Failure signals

- Agent performs customization without consent
- Agent treats skipped customization as onboarding failure

---

## 7. Case OC-06 — Existing config file must be preserved

### Setup

- `~/Documents/Life-Index/.life-index/config.yaml` already exists
- User changes default location only

### Expected behavior

- Agent preserves unrelated keys
- Only `defaults.location` is updated
- Final report notes the update clearly

### Failure signals

- Existing config content is lost
- Agent rewrites the file from scratch without preserving unrelated settings

---

## 8. Approval checklist

- [ ] Chinese entry prompt stays Chinese in the final report
- [ ] English entry prompt stays English in the final report
- [ ] Trigger customization edits only allowed `SKILL.md` surfaces
- [ ] `/life-index` remains preserved in trigger customization
- [ ] Default location preference is written to user config, not source code
- [ ] Runtime verification is reported honestly as verified or not verified
- [ ] Optional customization is clearly separated from installation success
