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

## How findings are worked

**Captured one by one, fixed in batches.** Each finding is written up here the moment it is reported, so nothing is lost and testing never waits on a fix. Fixes are then grouped into a **batch**: related use cases are worked together, on one branch, so shared root causes are found once rather than patched three times and the architecture updates stay coherent.

**Fixed immediately, out of band** — anything that blocks further testing, risks real data, or is a security hole.

## Status board

| # | Title | Reported | Verdict | Batch | Status | Closed by |
|---|-------|----------|---------|-------|--------|-----------|
| [UC-001](#uc-001--dashboard-should-cover-the-past-30-days-not-just-this-week) | Dashboard should cover the past 30 days, not just this week | 2026-07-30 | Spec gap | 1 — dashboard | Open | |
| [UC-002](#uc-002--dashboard-still-describes-itself-as-an-empty-app-shell) | Dashboard still describes itself as an empty app shell | 2026-07-30 | Bug | 1 — dashboard | Open | |
| [UC-003](#uc-003--per-lawyer-figure-counts-cases-opened-not-cases-handled) | Per-lawyer figure counts cases *opened*, not cases *handled* | 2026-07-30 | Bug | 1 — dashboard | Open | |

### Batch 1 — dashboard

All three sit in `reports/selectors.py` + `features/dashboard/`, and all three change the same API
fields and i18n keys. Fixing them together means one contract change, one set of translations and
one §10.1 rewrite instead of three overlapping ones.

---

### UC-001 — Dashboard should cover the past 30 days, not just this week

- **Reported:** 2026-07-30 by the user (project owner)
- **Area:** Dashboard (§10.1)
- **Verdict:** **Spec gap** — the code does exactly what the spec says; the spec is wrong about the office's needs
- **Status:** Open
- **Spec:** §10.1 — *"records entered **this week**, processes each user handled **this week**"*

**Actor & precondition**
Any signed-in user opening the Home dashboard.

**Steps**
1. Open the dashboard.
2. Read the headline figures ("New clients this week", "New cases this week", "Cases opened this week, by lawyer").

**Expected** — figures covering the **past 30 days**.

**Actual** — figures cover the current calendar week only, from Monday 00:00 (`reports/selectors.week_start`). On a Monday morning the dashboard is therefore almost entirely zeros, and any case worked the previous week disappears from view.

**Impact** — the dashboard is the landing page for every user. A 7-day window that resets each Monday makes it read as "nothing is happening" for a low-volume office where a single allocation spans weeks. Not a blocker; the Reports page (§10.2) already answers arbitrary date ranges.

**Scope (assessed, not yet built)**
- `reports/selectors.py` — `week_start()` → a rolling-window helper; `dashboard_stats()` uses it.
- **API field names change**, which is the real cost: `week_start`, `clients_this_week`, `processes_this_week`, `by_lawyer_this_week` all become window-neutral. Leaving a field called `..._this_week` holding 30 days would be a name that lies.
- `features/dashboard/types.ts` + `DashboardPage.tsx`; i18n keys `weekOf`/`clientsThisWeek`/`processesThisWeek`/`byLawyer` in **all three** locales.
- `reports` tests, including the query-count guard.

**Recommendation** — a fixed **rolling 30-day** window (today − 30 days), with neutral field names. A user-selectable window (7/30/90) is a small addition on top, but nobody asked for it and the Reports page already covers arbitrary ranges — so it stays out unless requested.

**Resolution** — _pending: §10.1 to be rewritten first (spec-gap rule), then built._

---

### UC-002 — Dashboard still describes itself as an empty app shell

- **Reported:** 2026-07-30, found while scoping UC-001
- **Area:** Dashboard (§10.1), i18n
- **Verdict:** **Bug** — user-visible text that is simply false
- **Status:** Open
- **Spec:** §10.1

**Steps** — open the dashboard and read the text under the title.

**Expected** — a description of the dashboard, or nothing.

**Actual** — `dashboard.subtitle` reads *"This is the application shell. Domain features arrive in the next iterations."* — a placeholder written in Iteration 0 and never removed. Present in all three locales.

**Impact** — cosmetic, but it is on the landing page and tells every user the product is unfinished. The same class of stale placeholder was just found in `docs/running.md` ("ships the shell only"), so it is worth grepping for others rather than fixing this one in isolation.

**Resolution** — _pending (batch 1)._

---

### UC-003 — Per-lawyer figure counts cases *opened*, not cases *handled*

- **Reported:** carried from the Iteration 4 review (2026-07-28); re-raised here because it is the same code as UC-001
- **Area:** Dashboard (§10.1)
- **Verdict:** **Bug** — the code does not do what the spec says
- **Status:** Open
- **Spec:** §10.1 — *"processes each user **handled**"*, aggregated over **`activity_log`**

**Expected** — per lawyer, the cases they actually **worked on** in the window, derived from `activity_log`.

**Actual** — `_by_lawyer(this_week)` counts processes **created** in the window and grouped by `assigned_lawyer`. A lawyer who spends the whole month progressing cases opened earlier shows **0**.

**Impact** — the figure is used to see who is busy, and it reports the opposite for exactly the lawyers doing the most continuing work. Widening the window to 30 days (UC-001) makes this *more* visible, not less, which is why it belongs in the same batch.

**Related, same area, needs a decision:** `user_report` (§10.2) omits lawyers with **zero** cases in range, so it cannot answer "who is idle?" — the mirror image of this defect.

**Resolution** — _pending (batch 1)._

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
