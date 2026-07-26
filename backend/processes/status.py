"""Per-step required-vs-missing status computation (§3.6, §5.4).

Pure functions — no writes, no audit. `save_step` (services) calls `compute_step_status` and
persists the result so list/badge queries stay index-fast. Note: the Step-1 generated-eligibility
requirement lands in Iteration 3; until then Step 1 completes on client papers + header fields.

`missing_requirements` is the single source of truth: a step is complete exactly when nothing is
missing, so the badge and the "proceed anyway?" warning can never drift apart.
"""

from catalog.institutes import codes_for_step

from .models import ProcessStep

# Controlled document types each step needs present to be "complete" (§3.6). Ordered for
# stable output — this list is rendered to the user in the proceed-anyway warning.
STEP1_REQUIRED_DOCS = ("ClientID", "RealEstate", "SignedAgreement")


# These helpers walk `.all()` and filter in Python on purpose: the detail endpoint prefetches
# documents/entries/steps, and `.filter()`/`.exists()` would bypass that cache and re-query per
# step (five steps → an N+1 on every case load).
def _present_doc_types(process, step_number) -> set[str]:
    return {d.document_type for d in process.documents.all() if d.step_number == step_number}


def _entry_complete(entry, step_number) -> bool:
    has_doc = bool(entry.documents.all())
    has_lawyer = entry.assigned_lawyer_id is not None
    if step_number == 2:
        return has_doc and has_lawyer and entry.approval_status != entry.ApprovalStatus.PENDING
    if step_number == 3:
        decided = entry.approval_status in (
            entry.ApprovalStatus.APPROVED,
            entry.ApprovalStatus.REJECTED,
        )
        return has_doc and has_lawyer and decided and entry.approval_date is not None
    if step_number == 4:
        return has_doc and has_lawyer
    return False


def _missing_fixed_institutes(process, step_number) -> list[str]:
    """Fixed institutes for this step that are absent altogether or not yet finished."""
    entries = {
        e.institute_code: e
        for e in process.institute_entries.all()
        if e.step_number == step_number and not e.is_custom
    }
    return [
        f"institute:{code}"
        for code in codes_for_step(step_number)
        if code not in entries or not _entry_complete(entries[code], step_number)
    ]


def missing_requirements(process, step_number, step_row) -> list[str]:
    """Stable codes for everything this step still needs — empty means complete (§3.6).

    Codes are machine-readable so the frontend can localize them (`institute:<code>`,
    `doc:<type>`, `step:<n>`, or a plain field name).
    """
    if step_number == 1:
        missing = []
        if not process.land_id:
            missing.append("land_id")
        if not process.category_id:
            missing.append("category")
        if process.duplicate_flagged:
            missing.append("duplicate_flag")
        present = _present_doc_types(process, 1)
        missing += [f"doc:{doc}" for doc in STEP1_REQUIRED_DOCS if doc not in present]
        return missing
    if step_number == 2:
        missing = [] if step_row.start_date else ["start_date"]
        return missing + _missing_fixed_institutes(process, 2)
    if step_number == 3:
        missing = _missing_fixed_institutes(process, 3)
        if step_row.out_of_city_flag:
            customs = [
                e for e in process.institute_entries.all() if e.step_number == 3 and e.is_custom
            ]
            if not customs or not all(e.custom_name and _entry_complete(e, 3) for e in customs):
                missing.append("custom_entries")
        return missing
    if step_number == 4:
        return _missing_fixed_institutes(process, 4)
    if step_number == 5:
        prior = sorted(
            (s for s in process.steps.all() if s.step_number < 5), key=lambda s: s.step_number
        )
        return [
            f"step:{s.step_number}" for s in prior if s.status != ProcessStep.Status.COMPLETE
        ]
    return []


def _step_has_data(process, step_number, step_row) -> bool:
    docs = [d for d in process.documents.all() if d.step_number == step_number]
    if step_number == 1:
        return bool(process.land_id or process.category_id or docs)
    if step_number == 5:
        return False  # Step 5 is derived from the others; it holds no data of its own
    has_entries = any(e.step_number == step_number for e in process.institute_entries.all())
    return bool(has_entries or docs or step_row.start_date or step_row.end_date)


def compute_step_status(process, step_number, step_row) -> str:
    """Derive not_started / in_progress / complete for one step (missing is set explicitly)."""
    if not missing_requirements(process, step_number, step_row):
        return ProcessStep.Status.COMPLETE
    if _step_has_data(process, step_number, step_row):
        return ProcessStep.Status.IN_PROGRESS
    return ProcessStep.Status.NOT_STARTED


def step_status_summary(process) -> dict:
    """Rollup for the process header/list badges (§5.4): per-step status + completed count."""
    steps = {s.step_number: s.status for s in process.steps.all()}
    completed = sum(1 for status in steps.values() if status == ProcessStep.Status.COMPLETE)
    return {"steps": steps, "completed": completed, "total": len(steps)}
