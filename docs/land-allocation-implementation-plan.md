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

This plan front-loads the demo and defers **OCR** (Iteration 5) and the **offline production deployment** (Iteration 7). That is safe:

- The app is **fully usable with manual data entry + imported PDFs from Iteration 2**. OCR only *auto-fills* fields, so deferring it costs nothing functionally — it's an enhancement, not a dependency.
- You still run a **minimal local dev environment** throughout (PostgreSQL + the Django and Vite dev servers). That is *not* "deployment" — the full offline Docker/LAN packaging, backups, and encryption are what's deferred to Iteration 7.
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
| 7 | Offline deployment, hardening & ops | Production-ready offline on the two computers | Data loss · at-rest · offline deploy | all |

**Showable milestones:**

- **End of Iteration 0** — a polished, fully-localized shell (language + RTL + light/dark) to align stakeholders on look & feel.
- **End of Iteration 2** — the **flagship demo**: create and run a complete case using imported PDFs. Genuinely usable for daily work with manual entry.
- **End of Iteration 4** — feature-complete for daily use (manual entry) — dashboards, reports, generated + compiled documents.
- **End of Iteration 6** — the paper-to-digital loop is complete (OCR auto-fill + camera scanning).
- **End of Iteration 7** — production-hardened offline deployment on the two office computers.

---

## Iteration 0 — Dev foundations & polished app shell

**✅ COMPLETE (2026-07-23).** Deviations recorded in architecture **§0** (notably: theme/language are client-only, not on `User`).

**Goal:** a running local dev environment and a clean, modern, fully-localized authenticated shell that is already worth showing.

**Tasks**

- [ ] Monorepo scaffold — `land-allocation/` with `backend/` (Django), `frontend/` (React + Vite), shared config — *§14*.
- [ ] **Minimal local dev runtime** (not production): PostgreSQL (local or a one-line docker) + Django dev server + Vite dev server. *Full offline Docker/LAN packaging is deferred to Iteration 7.*
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
- [ ] **Married beneficiary via scan** — marital status + the spouse's card in the same session, so `spouse_pid` is captured at creation. The backend already supports it (`confirm` with `client` + `client_version`); the create-a-client screen does not yet ask.
- [ ] **Re-file operation** — now only needed for a **category change** or a **PID correction**; a name edit no longer touches the filesystem — *§6.7*.

**Deliverable / demo:** photograph an ID → it reads in the background → review side-by-side → correct + confirm → the client, the case and the filed document all exist, with the file under the right category folder and the right name.

**Definition of Done:** uploads never block on the reading; a failed reading falls back cleanly to manual entry **and is still confirmable**; confirmation audited; corrected-vs-predicted pairs retained (in the append-only audit log).

**Still open:** only **one** real ID has been tested — do not tune the review screen's confidence thresholds until 15–25 real samples exist. PaddleOCR comparison not done. Married-beneficiary scanning and the re-file operation are the two remaining build items.

---

## Iteration 6 — Client-side scan capture

**Goal:** capture paper with the computer's own camera and feed it into the existing OCR/verify pipeline — fully offline.

**Tasks**

- [ ] Camera capture (`getUserMedia`) → canvas → multi-page PDF via bundled `pdf-lib` (no CDN); optional `opencv.js` enhance — *§6.1*.
- [ ] Same upload paths as import — `POST /documents/` for ordinary papers, `POST /card-scans/` for an ID (`input_source=scanned`). Both already accept images and convert server-side (It.5), so the camera path is a UI addition, not a new contract.
- [ ] (Optional) host **scanner-helper** (NAPS2/WIA on Windows, SANE on macOS) if a sheet-fed scanner is used — *§6.1, §2.5*.

**Deliverable / demo:** scan a multi-page document with the camera; it assembles into a PDF, uploads, and flows through reading → review → confirm like any import.

**Definition of Done:** scanning works from the client computer's own camera with no internet; the assembled PDF is valid and OCR-able.

---

## Iteration 7 — Offline deployment, hardening & operations

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
- **Manual/dev smoke** — exercise each new capability locally per iteration; **LAN / two-computer smoke starts at Iteration 7**.
- **High-stakes (Iteration 7)** — a documented, rehearsed restore drill; a performance run at target scale.

## Deferred / backlog (nice-to-have, out of the critical path)

- Sorani OCR fine-tuning (`tesstrain`) using the collected corrections dataset — pick up once enough verified pairs exist.
- WAL archiving for point-in-time DB recovery (beyond daily dumps).

---

*This plan is sequenced for an early demo (UI + backend first), deferring OCR and the offline production deployment to the end. The ordering — vertical slices, safety from day 0, and clean/localized UI throughout — is the part to preserve; adjust iteration boundaries to your team size.*
