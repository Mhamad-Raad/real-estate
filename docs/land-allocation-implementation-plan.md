# Land-Allocation System — Implementation Plan (Build Iterations)

**Companion to:** `land-allocation-architecture.md` (the full architecture spec). Section references like *§6.7* point into that document.
**Purpose:** turn the architecture into an ordered, incremental build. **This revision is sequenced to demo a working product as early as possible: UI + backend integration come first; OCR and the offline production deployment are deliberately moved to the end.**

---

## How to use this document

- Each **iteration** is a vertical slice (DB → API → UI) with a goal, a task checklist, a demoable deliverable, and a "Definition of Done" (DoD).
- Iterations are **ordered**; later ones build on earlier ones.
- Tasks are checkboxes so this file doubles as a live tracker.
- **Cross-cutting rules** (below) apply inside *every* iteration from the first line of code.

### Guiding principles

1. **Vertical slices, not layers.** Every iteration delivers a working path through the stack, so there's always something runnable to show.
2. **Show early.** The first iterations produce visible, localized UI backed by a real API — stakeholders see real progress fast.
3. **Safety is built in from day 0.** Soft-delete, audit, server-side permissions, and the duplicate rule are in the base models and first endpoints — never retrofitted.
4. **Clean, modern, fully-localized UI is a first-class goal — not a finishing touch.** Every screen ships polished and fully translated (Kurdish Sorani / Arabic / English) with correct RTL *in the iteration it is built*, not "styled later."
5. **Every iteration ends green.** Tests pass, the app runs, and the new capability is demoable.

### Sequencing note — build first, OCR & deployment later

This plan front-loads the demo and defers **OCR** (Iteration 5) and the **offline production deployment** (Iteration 9). That is safe:

- The app is **fully usable with manual data entry + imported PDFs from Iteration 2**. OCR only *auto-fills* fields, so deferring it costs nothing functionally — it's an enhancement, not a dependency.
- You still run a **minimal local dev environment** throughout (PostgreSQL + the Django and Vite dev servers). That is *not* "deployment" — the full offline Docker/LAN packaging, backups, and encryption are what's deferred to Iteration 9.
- **One honest tradeoff:** the Sorani-OCR accuracy spike (the biggest technical unknown) now lands at Iteration 5 rather than up front. **Recommendation:** run that ~1-day spike *in parallel, in the background* whenever someone has spare capacity before Iteration 5, so there are no surprises when you reach it.
  - **Outcome (2026-07-29): the spike ran at the start of It.5 and the deferral cost real rework.** Two of the plan's own assumptions were wrong — there is no `ckb` model, and pre-processing *lowered* accuracy — so §6.2 had to be rewritten and the tasks re-scoped mid-iteration. Nothing was lost, because OCR only auto-fills. **The lesson stands for the next unknown: a spike deferred is a plan written on a guess.**

### Cross-cutting concerns (apply to every iteration)

- [ ] **UI polish + full localization on every screen** — one consistent design system, responsive layout, light/dark, and complete `ckb`/`ar`/`en` translations with correct RTL, from the first screen — *§9*. **(Top priority.)**
- [ ] **Soft-delete + audit** on every new model/endpoint (inherit `SoftDeleteModel`; write `ActivityLog` from the service layer) — *§11*.
- [ ] **Server-side permissions** on every endpoint (never rely on UI hiding) — *§7*.
- [ ] **Optimistic locking** (`version`/`updated_at` → HTTP 409) on every writable resource — *§4.1, §12*.
- [ ] **Tests per feature** — model rules + the duplicate/soft-delete/audit invariants especially.
- [ ] **Indexes with the migration** that needs them — *§3.7*.

---

## Iteration summary

| # | Iteration | Primary outcome (demoable) | Key risk retired | Depends on |
|---|-----------|----------------------------|------------------|------------|
| 0 | Dev foundations & polished app shell | Localized, themeable, authenticated shell you can already show | Design-system + i18n/RTL foundation | — |
| 1 | Core domain + duplicate prevention | Create clients/processes + Step 1; dedup enforced | "No land twice" correctness | 0 |
| 2 | Documents (import) + 5-step workflow | Full case lifecycle with imported PDFs — **flagship demo** | Workflow complexity | 1 |
| 3 | Generated documents (template → PDF) | Eligibility + bulk list documents, print/save | Offline docx→PDF | 2 |
| 4 | Reports, dashboard, activities, compiled export | Leadership outputs + admin views | RTL/multilingual print | 2, 3 |
| 5 | OCR pipeline | Photograph an ID → draft → review → **confirmation creates the client, case and filed document** | Sorani OCR accuracy — **retired, see §6.2** | 2, 3 |
| 6 | Client-side scan capture | Scan with the camera into the pipeline | Offline browser scan-to-PDF | 5 |
| 7 | Real-data acceptance testing with the office | Every finding written up as a use case and closed; the specs match the real process | Does the built workflow match how the office actually works | 6 |
| 8 | Full-project review & hardening pass | One review report over the whole codebase — security, invariants, DRY, docs — findings fixed | Defects only a whole-project view reveals | 7 |
| 9 | Offline deployment, hardening & ops | Production-ready offline on the two computers | Data loss · at-rest · offline deploy | all |

**Showable milestones:**

- **End of Iteration 0** — a polished, fully-localized shell (language + RTL + light/dark) to align stakeholders on look & feel.
- **End of Iteration 2** — the **flagship demo**: create and run a complete case using imported PDFs. Genuinely usable for daily work with manual entry.
- **End of Iteration 4** — feature-complete for daily use (manual entry) — dashboards, reports, generated + compiled documents.
- **End of Iteration 6** — the paper-to-digital loop is complete (OCR auto-fill + camera scanning).
- **End of Iteration 7** — the office has run real allocations end to end; every finding is a written use case, triaged and closed.
- **End of Iteration 8** — the entire project has passed a single security / quality / architecture review.
- **End of Iteration 9** — production-hardened offline deployment on the two office computers.

---

## Iteration 0 — Dev foundations & polished app shell

**✅ COMPLETE (2026-07-23).** Deviations recorded in architecture **§0** (notably: theme/language are client-only, not on `User`).

**Goal:** a running local dev environment and a clean, modern, fully-localized authenticated shell that is already worth showing.

**Tasks**

- [ ] Monorepo scaffold — `land-allocation/` with `backend/` (Django), `frontend/` (React + Vite), shared config — *§14*.
- [ ] **Minimal local dev runtime** (not production): PostgreSQL (local or a one-line docker) + Django dev server + Vite dev server. *Full offline Docker/LAN packaging is deferred to Iteration 9.*
- [ ] Base models: `TimeStampedModel`, `SoftDeleteModel`, `ActiveManager`; `ActivityLog` + audit-service skeleton — *§3.1, §11*.
- [ ] JWT auth (SimpleJWT): `login`/`refresh`/`logout`/`me`; custom `User` with `role`, `language`, `theme` — *§7*.
- [ ] React app shell: routing, RTK Query `baseApi` (auth header + refresh-on-401), `auth` slice, protected routes, app layout (nav/sidebar/header), Login page — *§8*.
- [ ] **Design-system foundation (top priority):** Tailwind + shadcn/ui with a *customized* theme (not the default look), light/dark, consistent tokens (color, spacing, radius, typography), icon set, and a few polished shared components (buttons, inputs, cards, a data-table shell, toasts, skeleton loaders).
- [ ] **Localization foundation (top priority):** i18next with `ckb`/`ar`/`en`, per-user language switch, full RTL/LTR direction handling, **bundled** Arabic/Kurdish fonts (offline), bidi-safe number/date rendering — *§9*.

**Deliverable / demo:** log into a polished shell; switch language between Kurdish/Arabic/English with correct RTL flip; toggle light/dark. Already presentable.

**Definition of Done:** auth works locally; **every shell string is translated in all three languages with correct direction**; the design system + tokens are in place and look modern; login is audited.

---

## Iteration 1 — Core domain + duplicate prevention (polished UI)

**✅ COMPLETE (2026-07-23), incl. a hardening pass.** Added beyond spec: `Client.created_by`, `GET /lawyers/`; see architecture **§0**. Frontend has pagination on every list.

**Goal:** the data backbone and the most important business rule — a citizen cannot be granted land twice — behind clean, localized screens.

**Tasks**

- [ ] Models: `Category`, `Client` (all gov-ID fields + `marital_status`/`spouse_name`), `Process`, `ProcessStep` — *§3*. *(LandParcel was built here then removed in It.2.5 — land is now `Process.land_id`/`land_address`; see architecture §0.)*
- [ ] Migrations + indexes: `pid` partial-unique, `full_name`/`mother_full_name` trigram, `created_at`, composite filter index, **`process(client_id)` active-allocation partial-unique** — *§3.7*.
- [ ] CRUD APIs: users (admin), categories (admin), clients — *§4*. *(parcels endpoint removed It.2.5)*
- [ ] Process create (sets process-wide lawyer) + **Step 1** data entry (no OCR/generation yet).
- [ ] RBAC: `IsAdmin`, `IsProcessAssigneeOrAdmin`, field-level restrictions — *§7*.
- [ ] Duplicate check (PID exact / mother-name trigram) + **admin override** + `DuplicateOverride` log — *§5.7*.
- [ ] Processes list: search/filter by date, PID, name, category, status, lawyer + pagination — *§4.3*.
- [ ] Frontend (clean + localized): Users, Categories, Clients pages; Process-create + Step-1 form; duplicate-warning dialog; processes list with filters + a modern data table.

**Deliverable / demo:** create a client and a process, fill Step 1, find it in a filtered list; a duplicate is blocked and only an admin can override (logged).

**Definition of Done:** a lawyer can edit/soft-delete only their own processes; the "one active allocation per client" rule holds at the DB level (verified with a concurrent-insert test); every change audited; all new screens fully localized.

---

## Iteration 2 — Documents (import) + the full 5-step workflow

**✅ COMPLETE (2026-07-23).** Import path only (scan capture = It.6). Temporary simplifications vs spec — Step-1 completion doesn't yet require the eligibility PDF (It.3); document names are composed at upload not verification (It.5); `overall_status` has no `submitted` yet (It.4). All in architecture **§0**.

**Goal:** the heart of the app — the complete multi-step case with document attachment via the *import* path. **This is the flagship early demo.**

**Tasks**

- [ ] `Document` model + file-store service: category→person→document layout, stable-ID folders, `display_filename`, sanitization — *§6.7*.
- [ ] Upload endpoint (import path): PDF validation (magic bytes + size), `sha256`, write to disk — *§4.4*.
- [ ] Permission-checked download (`Content-Disposition` = `display_filename`).
- [ ] `ProcessInstituteEntry` model; shared **Institute enum** + read-only endpoint — *§3.4, §4*.
- [ ] Steps 2–4 APIs: per-institute entries + per-institute lawyer; Step-3 out-of-city custom rows; approvals/dates; end-date auto-set-but-editable — *§5*.
- [ ] Per-step status computation + `step_status_summary`; per-step save (`PATCH`, save-incomplete); Lawyer Notes; `overall_status` lifecycle — *§3.6, §5*.
- [ ] Frontend (clean + localized): accordion multi-step form with per-step save + status/color badges; institute dropdowns from the enum; repeatable custom rows; upload/import + download; Lawyer Notes.
- [ ] *(It.2.5)* **Progressive step unlocking for lawyers:** steps above `current_step` render locked; an explicit **Proceed** (confirm dialog listing what's still missing) calls `POST /processes/{id}/advance-step/` to unlock the next one. Forward-only; admins exempt — *§5.2, architecture §0*.

**Deliverable / demo:** build a complete case end-to-end by importing PDFs, saving steps incompletely, watching per-step badges update, and downloading documents with friendly filenames. **← First fully-usable, showable product** (manual entry + imports; no OCR/scan needed).

**Definition of Done:** a case can be fully assembled from imported files; missing-file indicators correct; downloads permission-checked; partial saves never force completion; the whole workflow is localized with correct RTL.

---

## Iteration 3 — Generated documents (offline template → PDF)

**Goal:** the system's own generated paperwork — no OCR involved. Stands up Celery + Redis + LibreOffice **locally** (for generation only; still not production deployment).

**Tasks**

- [x] `DocumentTemplate` model + stored `.docx` templates; template admin management (`.docx` upload) — *§3.5, §6.6, §6.8*. One active template per type (partial-unique index), admin-only `/document-templates/`, upload validates the file really opens as a Word template so a bad file fails at upload rather than mid-generation. **Admin screen** at `/templates`: upload, activate (retires the previous), soft-delete.
- [x] Eligibility generation: `docxtpl` fill → headless LibreOffice → PDF; stored as `system_generated`; regenerate supersedes. **One letter with both tables** (spouse cells blank when unmarried), not two PDFs — see §0 — and it is generated *by* completing Step 1, never required *for* it.
- [x] **Bulk document from the Processes page (§6.8):** checkbox multi-select (+ select-all) → `POST /processes/generate-document/` → letter page naming the first/last beneficiary, table on its own page → download/print; ids re-validated server-side; audited.
- [x] Frontend (clean + localized): generate / **in-page preview** / **print** / download in Step 1 (button unlocks when the step is complete, polls the job); Processes-list multi-select + "Print Step 1" toolbar action. **Template picker deliberately NOT built** (user decision, 2026-07-27): the office uses the same letter for Step 1 every time, so the bulk action uses the active `process_list` template. The `template` field on `POST /processes/generate-document/` stays as an optional override for future variants.

**Deliverable / demo:** complete Step 1 for a married client → base + spouse PDFs generated; select several rows on the Processes page → print a template document with their names auto-filled. High visual wow-factor (printable outputs).

**Definition of Done:** generation runs off the request path (Celery); RTL Sorani/Arabic renders correctly; generated docs stored/attached per §6.7 / §6.8; template management is admin-only.

---

## Iteration 4 — Reports, dashboard, activities, compiled export

**✅ COMPLETE (2026-07-28).** Notes: "mark-complete" already shipped in It.2, so It.4 covered four items, not five. `by_lawyer_this_week` counts cases *created* this week grouped by assignee, not cases *handled* via `activity_log` — a narrower reading of §10.1, still open. The compiled export ships with a **placeholder** summary `.docx` (as the letters did) — swapping in the office's own is an upload, no code change.

**Goal:** the outputs admins and leadership consume. After this the app is feature-complete for daily use with manual entry.

**Tasks**

- [ ] Step-5 compiled case: `.docx` summary → PDF, then merge all process PDFs (pypdf) into one file; print/export — *§10.3*.
- [ ] Mark-complete (respects the missing-file rule; admin can force) — *§5.1*.
- [ ] Home dashboard stats endpoint + UI: records this week, per-user counts, missing-file rollups — *§10.1*.
- [ ] Admin Reports (date + category filters) + export — *§10.2*.
- [ ] Activities page (audit-log view) with actor/entity/action/date filters — *§11.3*.
- [ ] Frontend (clean + localized): modern dashboard (charts/KPI cards), reports, activity log, compiled export.

**Deliverable / demo:** compile a finished case into a single leadership-ready PDF; view the dashboard, a filtered report, and the activity log.

**Definition of Done:** compiled export complete and correctly ordered; reports/activities admin-only (server-enforced); RTL/multilingual layout validated on real data; dashboards look modern and are localized.

---

## Iteration 5 — OCR pipeline

**Goal:** read a photographed ID card into the record it creates, with a human in the loop. (The app already works via manual entry, so this is an enhancement.)

> **⚠️ Rewritten mid-iteration (2026-07-29).** The spike disproved two assumptions in the original plan and the user chose a **scan-first** flow, so the tasks below describe what was actually decided and built. See §6.2/§6.5 and the deviations table at the top of the architecture doc.

**The flow, as built:** photograph the card **before any client exists** → staged PDF + reading → side-by-side review → **one confirmation creates client + case + filed document**. The store path is keyed by the PID and the person's name, both of which the card supplies — which is why a scan is staged and only filed on confirmation.

**Tasks**

- [x] **OCR spike** — Tesseract on a real KRG ID + a synthetic control. Findings: **no `ckb` model exists** (use the `Arabic` *script* model — 88% vs `ara`'s 68%); **pre-processing made it worse**; the **MRZ** (ICAO-9303, check-digit verified) is the reliable source — *§6.2, §6.5*.
- [x] Celery reading task: PDF→images (pdf2image), **no** OpenCV pre-processing, each side read **twice** (`Arabic` for names, `eng` for digits/MRZ), MRZ parser + positional front parser + front↔MRZ PID cross-check → `draft` with per-field confidence/source/verified + warnings — *§6.2*.
- [x] `CardScan` staging model + status lifecycle; **`manage.py sweep_card_scans`** re-enqueues readings whose task was lost and discards abandoned scans' files after 14 days (row kept) — *§6.3*.
- [x] Reading-status endpoint (`GET /card-scans/{id}/`) + staged-PDF preview endpoint — *§6.3*.
- [x] Confirm endpoint — creates client + case + filed document in one transaction, or updates an existing client under the optimistic lock (spouse card / re-scan); PID checked against the living population first so a misread is a **400 naming the conflict, not a 500**; audit records `corrected: [...]` — *§6.4, §6.5*.
- [x] Accept photographed IDs (JPEG/PNG/TIFF → PDF server-side), merge a card's **two sides into one PDF**, and reject unreadable files by parsing, not sniffing — *§6.1, §6.7*.
- [x] **Store layout revised** — `<CATEGORY>/<pid>/<institute>_<type>__<id>.pdf`: one folder per *person* (keyed by PID, not row id), and a short on-disk name because the folders already carry the category and the person. `display_filename` keeps the long download name. Data migration `documents/0004` moves existing files — *§6.7*.
- [x] **Household duplicate rule** — `Client.spouse_pid` + `clients.selectors.household_matches`: a married couple may hold one allocation, checked in both directions, re-derived on every edit and on card confirmation. Cleared on divorce — *§5.7*.
- [x] Frontend (clean + localized ckb/ar/en): side-by-side review screen; auto-fill from the `draft` with per-field source/confidence markers; **match-warning** gate before confirm; manual-entry fallback when the reading fails; RTK Query polling that stops on `done`/`failed`; camera capture + file picker for both sides.
- [x] **Married beneficiary via scan** — marital status on the scan screen; the spouse's card captured and read alongside the beneficiary's; the beneficiary's confirmation creates the record and the spouse's card is then filed onto it (the confirm response carries the client id + version for the second call). `spouse_pid` is captured at creation, so the household rule applies from the start — *§6.6, §5.7*.
- [x] **Re-file operation** — `documents/refile.py`, run on every client and process update. A **name** correction only rewrites `display_filename`; a **category change** or **PID correction** moves the files (on commit, audited, short id preserved), and emptied person folders are pruned — *§6.7*.

**Deliverable / demo:** photograph an ID → it reads in the background → review side-by-side → correct + confirm → the client, the case and the filed document all exist, with the file under the right category folder and the right name.

**Definition of Done:** uploads never block on the reading; a failed reading falls back cleanly to manual entry **and is still confirmable**; confirmation audited; corrected-vs-predicted pairs retained (in the append-only audit log).

**Still open:** only **one** real ID has been tested — do not tune the review screen's confidence thresholds until 15–25 real samples exist. PaddleOCR comparison not done. All build items are complete.

---

## Iteration 6 — Client-side scan capture

**Goal:** capture paper with the computer's own camera and feed it into the existing OCR/verify pipeline — fully offline.

**Tasks**

- [x] Camera capture (`getUserMedia`) → canvas → multi-page PDF via bundled `pdf-lib` (no CDN) — *§6.1*. **`opencv.js` enhance deliberately not built** (the §6.2 spike measured pre-processing as harmful; ~9 MB WASM for no demonstrated gain).
- [x] Same upload paths as import — `POST /documents/` for ordinary papers, `POST /card-scans/` for an ID (`input_source=scanned`). Both already accept images and convert server-side (It.5), so the camera path was a UI addition, not a new contract.
- [ ] (Optional) host **scanner-helper** (NAPS2/WIA on Windows, SANE on macOS) if a sheet-fed scanner is used — *§6.1, §2.5*.

**Deliverable / demo:** scan a multi-page document with the camera; it assembles into a PDF, uploads, and is filed like any import. *(Reading → review → confirm applies to identity cards only — an ordinary scanned paper is archived, not OCR'd.)*

**Definition of Done:** scanning works from the client computer's own camera with no internet; the assembled PDF is valid and OCR-able.

**Status: DONE apart from the optional scanner-helper (2026-07-30).** Shared `useCamera` hook + `lib/pdfAssembly.ts` + `ScanDocumentDialog` (multi-page capture, reorder, remove, size guard), offered beside *Import PDF* on every Step 1–4 slot, localized ×3 with RTL. Verified in a real browser against a synthetic camera: two shots captured with the camera held open between them, reordered, uploaded 201, stored as a genuine 2-page PDF with `input_source=scanned`.

---

## Iteration 7 — Real-data acceptance testing with the office

**Goal:** the lawyers who will actually use this run **real allocations with real data** through the built product, and every finding they report becomes a **written use case** that is triaged and closed — updating the specs *before* deployment freezes them.

This is the first iteration whose input comes from outside the code. The office reports what happened; each report is written up as a use case, given a verdict, and either fixed, specified, or deliberately declined. Expect a meaningful share to land in the **architecture doc**, not just the code — a mismatch between the built workflow and the office's real process is a *spec* defect, and §-level updates plus dated deviation entries are the deliverable, not an afterthought.

**Tasks**

- [ ] **Run the real process end to end** — the office creates and works genuine allocations: client + Step 1, institutes in Steps 2–4, generated eligibility and list letters, Step-5 compiled export. On the real two-computer setup wherever possible.
- [ ] **Every finding becomes a use case** in `docs/use-cases.md`: actor, precondition, steps taken, expected vs actual, and a **verdict** — *bug* · *spec gap* · *change request* · *works as intended (misunderstanding)*.
- [ ] **Triage and close each one:** a bug gets a fix **plus a regression test**; a spec gap updates the architecture § first and is then built; a change request is scoped and decided before any code moves.
- [ ] **Propagate to the docs** — §-level architecture updates, plus a dated deviation entry for anything that contradicts the current spec. The docs must describe what the office actually does.
- [ ] **Re-verify per change:** both suites green, and a browser smoke of each changed flow in `ckb`/`ar`/`en`.
- [ ] **Collect 15–25 real ID cards** (with some genuine photocopies) while real scanning is happening, and **tune the OCR confidence threshold** against them — *§6.2*. This iteration is the natural place to retire that long-standing blocker.
- [ ] **Separate pilot data from dev/test data** — clean the dev DB before the pilot and account for what the pilot creates, so real records are never confused with smoke data.

> **⚠️ Data-handling rule for this iteration — real citizen data.** Pilot data is real people's national IDs. **Never commit ID images or scans** (`.gitignore` blocks image files — keep it that way, and never `git add -A`), never paste identifying extracts into a chat or an issue, and share findings in **aggregate or redacted** form. A privacy incident already happened once on this project (2026-07-29); the rule exists because of it.

**Deliverable / demo:** a use-case log where every reported finding has a verdict and, where applicable, the commit that closed it — and specs that match the office's real process.

**Definition of Done:** the office confirms the workflow matches how they actually work; no known correctness or usability blocker remains; the architecture doc reflects reality; both suites green.

---

## Iteration 8 — Full-project review & hardening pass

**Goal:** one deliberate review of the **entire project** — not a diff — for security, correctness, architecture conformance, DRY, dead code, documentation and lint, with every finding fixed or explicitly deferred with a reason.

Previous reviews in this project were per-iteration and scoped to what had just changed. This one is whole-codebase, and exists to catch what only a project-wide view reveals: an invariant that silently stopped holding somewhere, the fourth copy of a helper, a stale doc claim, an endpoint whose permissions drifted. **Every finding is probed before it is claimed** — that standard is what has made the previous reviews worth the time.

**Tasks**

- [ ] **Security review of the whole surface** — authn/authz on *every* endpoint against the §7 RBAC matrix; input validation; file handling and path traversal; CSV injection; secrets handling; error/stack-trace leakage; refresh-token handling — *§7, §12*.
- [ ] **Invariant audit, endpoint by endpoint** — soft-delete everywhere, append-only audit written only from services, the two partial-unique "no land twice" indexes, optimistic locking on every writable resource. Each one **proven by a test**, not by reading — *§3.7, §11, §12*.
- [ ] **Architecture conformance** — thin views → services → selectors; RTK Query owning all server state; the institute list defined once; indexes shipped with their migrations — *§14*.
- [ ] **DRY + dead-code sweep** across backend and frontend. This project has repeatedly found third and fourth copies of the same helper; assume more exist.
- [ ] **Bug & logic hunt** — N+1 queries, race conditions, transaction boundaries, `on_commit` correctness, timezone/date handling, i18n digit and pluralization handling.
- [ ] **Lint, type and build clean** across the whole tree — including the two long-standing `only-export-components` warnings.
- [ ] **Test-quality audit** — find tests that silently skip, assert nothing, or cover a mock instead of the code; verify the invariants are actually covered.
- [ ] **Documentation reconciliation** — architecture doc vs shipped reality, this plan's checkboxes, `running.md`, and **settle whether `CLAUDE.md` is tracked in git** (it is currently gitignored, so a fresh clone gets outdated OCR guidance).

**Deliverable / demo:** a written review report — findings ordered by severity, each with the probe that proved it and either the commit that fixed it or the reason it was deferred.

**Definition of Done:** no known security defect; every invariant proven by a test; lint/type/build clean; the documentation matches the code.

---

## Iteration 9 — Offline deployment, hardening & operations

**Goal:** make it production-safe and truly offline on the two office computers: containerized, on the LAN, encrypted, backed up, restore-tested, and tuned.

**Tasks**

- [ ] Dockerize the full stack + **offline image save/load** (`docker save`/`load`); Nginx serving static build + reverse-proxy; one-command bring-up — *§2.3*.
- [ ] Fixed-IP LAN + **two-computer validation**; Windows-production / macOS-development parity; Desktop data-root wiring — *§2, §2.5*.
- [ ] Full-disk encryption: **BitLocker** (Windows) / **FileVault** (macOS); encrypt the external drive — *§12, §2.5*.
- [ ] Backup automation: **Celery Beat** `pg_dump` into `Desktop/db-backups` (DB-first), native scheduler copies the Desktop data folder → external drive; manifest + rotation (14 daily / 8 weekly, 2 drives) — *§13.2*.
- [ ] **Tested restore drill** + written runbook (files + DB + integrity check) — *§13.3*.
- [ ] TLS on Nginx (self-signed) option; refresh-token handling decision — *§12*.
- [ ] RTL/multilingual **print validation** on real documents; performance pass at scale (seed tens of thousands; verify index usage) — *§13.1*.
- [ ] Re-file operation for category/name changes; filename sanitization + optional Latin-transliteration toggle — *§6.7*.
- [ ] Security review, secrets handling, host hardening (firewall, no egress) — *§12*.

**Deliverable / demo:** the full stack runs offline on the two computers over the LAN; a daily backup runs to the external drive and a restore is performed successfully.

**Definition of Done:** data encrypted at rest; a restore has been *proven*; the app stays fast at scale; security checklist signed off.

---

## Testing & acceptance strategy (per iteration)

- **Unit** — model rules, status computation, permission classes, filename sanitization.
- **Invariant tests (critical)** — soft-delete hides rows everywhere; audit captures before/after; duplicate rule blocks a second active allocation under concurrent inserts; optimistic-lock returns 409 on a stale write.
- **API tests** — role matrix (Admin vs Lawyer, assignee vs non-assignee) per endpoint.
- **Localization checks** — every screen has no hard-coded strings; RTL renders correctly for `ckb`/`ar`; numbers/dates use bidi-safe rendering.
- **Manual/dev smoke** — exercise each new capability locally per iteration; **LAN / two-computer smoke starts at Iteration 9**.
- **High-stakes (Iteration 9)** — a documented, rehearsed restore drill; a performance run at target scale.

## Deferred / backlog (nice-to-have, out of the critical path)

- Sorani OCR fine-tuning (`tesstrain`) using the collected corrections dataset — pick up once enough verified pairs exist.
- WAL archiving for point-in-time DB recovery (beyond daily dumps).

---

*This plan is sequenced for an early demo (UI + backend first), deferring OCR and the offline production deployment to the end. The ordering — vertical slices, safety from day 0, and clean/localized UI throughout — is the part to preserve; adjust iteration boundaries to your team size.*
