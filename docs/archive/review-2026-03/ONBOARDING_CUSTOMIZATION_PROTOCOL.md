# Onboarding Customization Protocol

> **Document role**: Define the governed post-install customization step for agent-led onboarding
> **Audience**: Project owner, onboarding agents, reviewers, future maintainers
> **Authority**: Review-scoped execution protocol; permanent runtime truth must be promoted to Tier 1 SSOT
> **Primary goal**: Allow safe post-install personalization without blurring installation, runtime SSOT, and source-code boundaries

---

## 1. Why this protocol exists

Life Index is an **agent-first / agent-native application**.

That means onboarding does not have to stop at “the software is installed.”
An onboarding agent may also help the user complete a narrow, explicit personalization step **after** installation and first-run verification succeed.

This protocol exists to govern two supported post-install customization actions:

1. **Trigger-word customization** in `SKILL.md`
2. **Default-location customization** in user config

The goal is to make this behavior:

- explicit
- bounded
- reviewable
- honest about runtime gaps

---

## 2. Scope

This protocol applies only to the **optional final stage** of onboarding, after the agent has already completed:

1. clone
2. venv
3. install
4. index
5. health
6. first write
7. first search

This protocol does **not** replace installation.
It defines an **optional personalization step** that happens only after successful verification.

---

## 3. Supported customization actions

## 3.1 Trigger-word customization

### Product stance

Agents should explain that, to improve Life Index trigger success rate in current Agent / LLM ecosystems, the user should provide a custom trigger phrase.

The best-practice pattern must be presented clearly as:

`"/life-index" + "user custom trigger phrase" + "journal content"`

Agents should give concrete examples such as:

- `/life-index 记日志: 今天状态不错`
- `/life-index note this: 刚刚看到一篇文章很有启发`

Then agents should ask the user to provide the trigger phrase they want to use. If the user does not want to set one now, they may explicitly reply `skip` / `跳过`.

This is a product-level onboarding recommendation backed by real-world usage validation.
Do not replace it with a different trigger strategy during onboarding.

### Supported action

If the user agrees, the onboarding agent may update the trigger definitions in `SKILL.md`.

### Allowed target

- `SKILL.md` YAML frontmatter `triggers:` array
- Trigger examples / trigger table entries in `SKILL.md` that must stay consistent with the frontmatter

### Required constraints

- Keep `/life-index` itself
- Add the user phrase in the form the user requested
- If documenting the pattern explicitly, use the combined form the owner specified (for example: `/life-index log this`)
- Maintain valid YAML and valid markdown
- Keep trigger examples synchronized with the actual trigger list

### Not allowed

- Do not rewrite unrelated parts of `SKILL.md`
- Do not remove the base `/life-index` trigger
- Do not invent a new trigger strategy
- Do not modify `docs/API.md`, `docs/ARCHITECTURE.md`, or package metadata to support this

---

## 3.2 Default-location customization

### Product stance

Current product rule for missing location remains:

1. tool defaults to `Chongqing, China`
2. tool writes the journal
3. agent asks for confirmation after write

This protocol does **not** change that product rule.

### Supported action

If the user wants a different personal default address, the onboarding agent may create or update:

`~/Documents/Life-Index/.life-index/config.yaml`

with:

```yaml
defaults:
  location: "<City, Country>"
```

### Allowed target

- User config file only: `~/Documents/Life-Index/.life-index/config.yaml`

### Required constraints

- Use `config.example.yaml` as the schema reference
- Ask for `City, Country` format explicitly
- Preserve unrelated config fields if the file already exists
- Report truthfully whether the setting is only recorded or also verified as active at runtime

### Important runtime honesty rule

The repository currently contains configuration infrastructure for default location, but the active write path must be treated as **not fully verified to consume this value automatically** until explicitly proven in rehearsal.

Therefore the onboarding agent must distinguish between:

- **preference recorded**
- **runtime behavior verified**

### Not allowed

- Do not modify `tools/lib/config.py`
- Do not modify `tools/write_journal/core.py`
- Do not silently claim the new default is active unless it was explicitly verified

---

## 4. Customization stage placement

The onboarding flow becomes:

```text
Install → Initialize → Health Check → First Write → First Search → Optional Customization
```

Customization is allowed **only after** the first write/search verification succeeds.

Reason:

- installation success must stay separable from personalization
- failures in customization must not be misreported as installation failure
- the agent should first prove the base system works before changing local behavior

---

## 5. Agent interaction contract

## 5.1 Report language

If the onboarding entry prompt is Chinese, the final report must be Chinese.

If the onboarding entry prompt is English, the final report must be English.

This rule applies to both:

- the installation summary
- the optional customization summary

## 5.2 Customization questions

After successful installation verification, the agent may ask the user these two questions in sequence:

1. trigger customization question
2. default-location customization question

The agent should not batch both together if that makes the interaction harder to follow.

### Trigger question intent

Recommend the pattern:

`/life-index` + `用户自定义触发词`

### Location question intent

Explain that the current system default is `Chongqing, China`, and ask whether the user wants to record a different preferred default address.

---

## 6. Allowed / forbidden operations summary

| Surface | Allowed | Forbidden |
|:---|:---|:---|
| `SKILL.md` trigger section | Add/update user-approved triggers; sync trigger examples | Rewriting unrelated workflow sections; removing `/life-index` |
| `~/Documents/Life-Index/.life-index/config.yaml` | Create/update `defaults.location`; preserve existing keys | Overwriting unrelated settings blindly |
| `tools/` source files | None | Any runtime/source-code modification during onboarding |
| Tier 1 API/architecture docs | None during onboarding execution | Editing SSOT docs as part of user installation |

---

## 7. Verification rules

## 7.1 Trigger customization verification

Minimum verification:

- read back the edited `SKILL.md`
- confirm the user-requested trigger phrase now appears in the trigger list and examples
- confirm `/life-index` remains present

Do not claim host-platform reload happened unless it actually did.

## 7.2 Default-location customization verification

Minimum verification:

- read back the saved `config.yaml`
- confirm `defaults.location` matches the user request

If runtime verification is attempted, report the result explicitly.

If runtime verification is not attempted or is inconclusive, report:

- preference saved
- runtime activation not yet verified

---

## 8. Required final report additions

If customization was attempted, the final report should add a short section such as:

```text
**Customization**:
- Trigger phrase: <configured / skipped>
- Default location preference: <saved / skipped>
- Runtime verification of default location: <verified / not verified>
```

This section must not blur installation success with customization success.

---

## 9. Relationship to Tier 1 truth

Per `DOCS_BOUNDARY_PLAN.md`:

- `SKILL.md` owns runtime trigger truth
- `docs/API.md` owns tool/config interface truth
- this document only governs the onboarding execution protocol

If the customization rules become stable project truth, they must be promoted upstream and this file should then point to the adopted Tier 1 wording.

---

## 10. Bottom line

Life Index onboarding may end with a narrow, explicit, agent-led personalization step.

That step is valid only if it stays:

- user-approved
- bounded to the correct surfaces
- truthful about runtime verification
- clearly separated from installation success itself
