# Iteration 8 — Full-project review report

**Date:** 2026-08-06 · **Branch:** `dev`, from `baab1c5` · **Scope:** the entire codebase, not a diff.

Every finding below was **probed before it was claimed** — the probe is named with each one. Two
suspicions died under probe and are recorded as such, because "we checked and it holds" is worth
as much to the next reader as a defect is.

**Baseline before any change:** 408 backend tests (container, 0 skips) · 97 frontend · `tsc -b`
clean · build clean · `oxlint` 2 warnings.
**After:** **415 backend** (container 0 skips; native 11 LibreOffice skips) · **99 frontend** ·
`tsc -b` clean · build clean · **`oxlint` silent**.

---

## Findings by severity

### 1 · HIGH — Django's admin site was a second, unaudited write path into every table

`django.contrib.admin` was scaffolded in It.0 and never revisited. It registered ModelAdmins for
`Client`, `Process`, `ProcessStep`, `Document`, `Category`, `User` and `DuplicateOverride`, and it
writes **straight to the tables** — past the service layer, so past soft-delete, past the audit
log, past optimistic locking, past the duplicate rules.

**Probe** (`common/test_probe_admin.py`, temporary): a staff account posted the admin's own delete
form.

```
DELETE status: 200
row still in all_objects: False      ← the manager that is supposed to see everything
audit DELETE rows: 0
document hard-deleted: True
process change form status: 200
```

A `Document` row — the archive's pointer to a scanned government paper — was **hard-deleted with
zero audit rows**, leaving its file orphaned on disk. `PROTECT` saved only *referenced* parents (a
client with a live case survived); every leaf row was reachable. This defeats the two invariants
the whole design rests on (§11.1, §11.2) from inside the boundary meant to enforce them.

**Fixed** — `3ec1125` + `14ccdbc`. The admin app is uninstalled and unmounted; the seven `admin.py`
modules are gone. Nothing needed it: the app has its own Users screen, restore desk (UC-063) and
audit trail (§11.3). Pinned by `NoSecondWritePathTests`, which fails if the app is ever installed
again. `§12` now records it.

*Left alone:* the `django_admin_log` table remains in the database, unwritten and unreferenced.
Dropping a table is riskier than leaving one dormant; It.9's DB-role work is the right place.

### 2 · MEDIUM — a lawyer could open a case in another lawyer's name

`ProcessViewSet.perform_create` has always forced a lawyer's own id onto a new case (§7.2 layer 4).
Confirming a scanned card **also opens a case**, and that path passed the request's
`assigned_lawyer` straight through. Since `assigned_lawyer` is deliberately not editable
afterwards, the mistake would have been permanent.

**Probe** (`common/test_probe_rbac.py`, temporary) — same act, two doors, as `lawyer_a`:

```
POST /processes/            assigned_lawyer=lawyer_b  → 201, case assigned to: lawyer_a   ✅ rule held
POST /card-scans/{id}/confirm/  assigned_lawyer=lawyer_b  → 200, case assigned to: lawyer_b   ❌ rule bypassed
```

The same serializer also used `User.objects.filter(is_active=True)` instead of the shared
`AssignableLawyerField`, so §7.2 layer 6 (assignability) was bypassed too — equivalent only for as
long as soft-deleting a user keeps deactivating them.

**Fixed** — `3085699`. Three regression tests: a lawyer's choice is overridden, an admin's is
honoured, and a lawyer who has left is a 400.

### 3 · MEDIUM — the test suite wrote real `.docx` files into the office's template directory

Batch 24 fixed this class for `DOCUMENTS_ROOT` by redirecting it under `TESTING`. `LETTER_TEMPLATES_ROOT`
was deliberately left pointing at the **configured** root, on the belief that the rendering tests
read the installed templates. They do not — every test that renders one builds it or installs it
into a root it overrides itself. So isolation depended on each class remembering
`@override_settings`, and the classes that forgot wrote into the live directory.

**Probe:** five `test summary__*.docx` files appeared in `LandAllocationData/documents/_templates/`
during this review, timestamped 08:58, 09:00 and 09:19 — one per suite run.

**Fixed** — `14ccdbc`. Redirected to a temp dir under `TESTING`, the same structural fix as
`DOCUMENTS_ROOT`. Verified by re-running the suite: it now creates nothing in the repo.

### 4 · MEDIUM — `LandAllocationData/` was not gitignored, and it is where documents default to

`.gitignore` blocked `/data/` — a path nothing writes to. The backend's default `DOCUMENTS_ROOT` is
`BASE_DIR.parent / "LandAllocationData" / "documents"`, which on a native run resolves **inside the
repo**. Citizen PDFs were one `git add -A` from being committed, in a project that already had a
privacy incident (2026-07-29) and whose own rule is "never `git add -A`".

**Fixed** — `4917c79`. Both paths ignored, with the reason in the file.

### 5 · MEDIUM-LOW — two unhandled exceptions surfaced as 500s

**Probe** (`common/test_probe_errors.py`, temporary):

```
PATCH with version='not-a-number'  -> 500     (int() raised ValueError; DRF does not translate it)
POST  /categories/999999/restore/  -> 500     (all_objects.get() raised DoesNotExist)
POST  /users/999999/restore/       -> 500
GET   /processes/1/steps/9/        -> 404     ✅ already correct
```

The restore one is genuinely reachable: the restore desk is a list two office computers share, so
it goes stale. And with `DEBUG` on, a 500 answers with a full stack trace.

**Fixed** — `e9e1b22`: 400 and 404 respectively, with regression tests on both.

### 6 · MEDIUM-LOW — `DEBUG` defaulted to `True`

A production host that never set `DJANGO_DEBUG` would boot into debug: stack traces to any LAN
client, and `ALLOWED_HOSTS` silently unenforced. **Fixed** — `14ccdbc`: defaults to off, so the
default fails in the safe direction. Dev sets it explicitly in `.env`, which `running.md` already
requires as step one. The insecure-secret guard now skips under `manage.py test`, so a fresh clone
with no `.env` can still run the suite.

### 7 · LOW — an oversized upload was read into memory before the size check

`upload.read()` ran first and `len(content) > limit` second, so a 2 GB upload became 2 GB of worker
RSS before its 413. **Fixed** — `read_upload()` asks the upload for its size first; used by both
the document and card-scan endpoints.

### 8 · LOW — the compiled-case test was missing the guard its siblings carry

`documents/test_compile.py::test_failure_marks_the_job_failed_with_a_reason` needs real LibreOffice
(the cover sheet renders before the merge reads the files). Without the `skipUnless` its siblings
have, it left the suite **red** on the documented native-dev path — `'missing' not found in
'LibreOffice binary not found: soffice'`. `HAS_LIBREOFFICE` was also declared twice.

**Fixed** — `4917c79`: one declaration in `documents/factories.py`, the guard applied.

**⚠️ And it bit me back.** Removing the now-unused `import shutil` from `test_rendering.py` broke
`addCleanup(shutil.rmtree, …)` — invisible natively, because that whole class *skips* there. Four
errors in the container. Fixed in `3bc5262`. **The lesson is the finding's own lesson: a skipped
test hides a real break, and the native suite cannot verify anything about the code it skips.**

---

## Quality work (no defect, but the codebase is better for it)

- **The workflow length was declared in eight places** — four backend, two frontend, plus a
  hand-written `[1-5]` URL regex and a step-5 literal. Now `processes/constants.py` and a frontend
  `STEP_NUMBERS`. This is direct preparation for UC-043 (5 steps → 7), which was going to require
  finding all eight by hand — `aa44d5b`.
- **`ProcessStep.approval_status` dropped** — §0 has listed it as dead since It.2.5. Nothing could
  write it (never in `EDITABLE_STEP_FIELDS`) and nothing read it, but it was still serialized into
  every step payload, inviting a future reader to trust it. Migration `0012`, applied cleanly
  against the real dev DB — `584ecd1`.
- **The two long-standing `only-export-components` warnings are gone** — `buttonVariants` was an
  export nothing imported, and the imperative `toast` moved out of the component module into
  `lib/toast.ts` (30 files repointed). `oxlint` is now silent — `3af525c`.
- **Dead code:** `components/ui/combobox.tsx`, 177 lines, referenced nowhere. Deleted.
- **DRY:** `CardReviewPanel` hand-rolled the blob fetch that `fetchBlobUrl` already does.
- **Tokens moved to `sessionStorage`** (the user's decision) — see below.

---

## The session-storage decision

The spec said memory or an httpOnly cookie; the code used `localStorage`. On **shared** office
computers with a 7-day refresh window (UC-071), that meant whoever opened the browser next morning
arrived signed in as the previous lawyer — their menu, their cases, their name on every audited
write.

Settled as **`sessionStorage`, both halves** — `68204ea`. A reload or navigation stays seamless
(which is all UC-071 actually asked for); closing the browser ends the session. Cost: a second tab
signs in on its own. Old `localStorage` tokens are cleared on load so none can linger out its week.

**httpOnly cookies were considered and deferred to It.9, deliberately.** They answer a *different*
threat — a script reading the token — and this bundle has no third-party script, no CDN and no
`innerHTML` sink (checked). They also need TLS to be worth setting and bring CSRF back, which the
header-borne JWT avoids. The trap recorded in §7.1 for whoever does it: a **persistent** httpOnly
cookie re-introduces exactly the shared-machine exposure removed here.

---

## Probed and DISPROVEN — do not re-raise

- **N+1 queries.** Measured with `CaptureQueriesContext` as rows went 3 → 12: processes list 2→2,
  activities 2→2, clients 2→2, dashboard 12→12 (constant aggregates), process detail 4, documents
  list 1, restore desk 1. **Every delta was 0.** The `select_related`/`prefetch_related` work from
  earlier iterations holds.
- **Tests that assert nothing or cover a mock.** An AST scan of every backend test function and
  every frontend `it()` found **0** without an assertion (108 frontend cases). Mocking is sparse and
  sits only at the OCR engine boundary, which is correct — Tesseract needs real cards.
- **Path traversal in the file store.** `sanitize()` strips `/`, `\` and control characters, then
  strips leading/trailing dots — `".."` collapses to the fallback. Lookups go through
  `Document.file_path`, never a supplied name.
- **Unused backend code.** 170 top-level functions scanned; **0** unreferenced. `parcels/` is
  deliberately retained for migration history and stays.
- **Invariant coverage.** All FKs are `PROTECT` (0 exceptions), no signals write audit, both
  partial-unique indexes exist in the live DB, and `check_version(required=True)` guards every
  update path.

---

## Deferred to It.9, with reasons

Added to the plan as explicit tasks rather than left as prose:

| Item | Why not now |
|------|-------------|
| **A real `/health/` readiness check** (DB, Redis, file store) | It answers a static `ok` today. The restore drill depends on it, and it belongs with the Compose healthchecks. §4.2 now says plainly that it is liveness-only. |
| **Production account bootstrap** | `seed_dev` is the only documented path to a first user and ships `admin`/`admin12345` as a superuser. Dev-only by its docstring; nothing fills the gap. |
| **Login rate-limiting** | No throttling anywhere, so guessing from the second computer is unbounded. Cheap with `ScopedRateThrottle`, but with several Gunicorn workers the default local-memory cache counts per worker — it needs the deployment topology It.9 defines. |
| **httpOnly refresh cookies + TLS** | As above — worth doing, worth doing together. |

**`CLAUDE.md` stays gitignored** (the user's decision, 2026-08-06). `docs/` remains what a fresh
clone gets.

---

## Definition of Done

- [x] No known security defect — 8 findings, all fixed.
- [x] Every invariant proven by a test — including the new one that keeps the admin site out.
- [x] Lint / type / build clean — `oxlint` silent for the first time since It.0.
- [x] The documentation matches the code — §4.2's endpoint reference had 7 wrong or missing rows.
