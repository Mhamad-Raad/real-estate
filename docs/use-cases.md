# Use cases — real-data acceptance testing (Iteration 7)

Every finding the office reports while running **real allocations with real data** is written up here as a use case, given a verdict, and closed. This file is the iteration's deliverable.

**Companion docs:** `land-allocation-architecture.md` (§-refs point into it) · `land-allocation-implementation-plan.md` (Iteration 7).

> **⚠️ Real citizen data.** Pilot findings concern real people's national IDs. **Never paste identifying data into this file** — no PIDs, no full names, no ID images. Refer to a record as `client #id` or "the beneficiary in case 42". Never commit scans (`.gitignore` blocks image files; never `git add -A`). A privacy incident already happened on this project on 2026-07-29 — this rule is why.

## Verdicts

| Verdict | Meaning | What happens |
|---|---|---|
| **Bug** | The code does not do what the spec says | Fix **plus a regression test** |
| **Spec gap** | The code matches the spec, but the spec is wrong about the office's real process | Update the architecture § **first**, then build |
| **Change request** | New behaviour nobody specified | Scope and decide before any code moves |
| **Works as intended** | Behaviour is correct; the expectation was mistaken | Close with the explanation — and ask whether the UI misled them |

## Status board

| # | Title | Reported | Verdict | Status | Closed by |
|---|-------|----------|---------|--------|-----------|
| — | _none yet_ | | | | |

---

## Template

Copy this block for each new finding.

```markdown
### UC-001 — <short title>

- **Reported:** YYYY-MM-DD by <role, e.g. "lawyer A">
- **Area:** <Step 1 / institutes / letters / scanning / reports / …>
- **Verdict:** Bug | Spec gap | Change request | Works as intended
- **Status:** Open | In progress | Closed
- **Spec:** §<section>, or "unspecified"

**Actor & precondition**
Who was doing what, and what state the case was in.

**Steps**
1. …
2. …

**Expected** — what the office expected to happen, and why.

**Actual** — what happened. Include the exact message or screenshot reference (redacted).

**Impact** — who is blocked, how often, and whether a workaround exists.

**Resolution** — the decision, the commit(s), the test that pins it, and any architecture § updated.
```
