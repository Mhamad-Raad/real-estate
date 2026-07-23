"""Per-step required-vs-missing status computation (§3.6, §5.4).

Pure functions — no writes, no audit. `save_step` (services) calls `compute_step_status` and
persists the result so list/badge queries stay index-fast. Note: the Step-1 generated-eligibility
requirement lands in Iteration 3; until then Step 1 completes on client papers + header fields.
"""

from catalog.institutes import codes_for_step

from .models import ProcessStep

# Controlled document types each step needs present to be "complete" (§3.6).
STEP1_REQUIRED_DOCS = {"ClientID", "RealEstate", "SignedAgreement"}


def _present_doc_types(process, step_number) -> set[str]:
    return set(
        process.documents.filter(step_number=step_number).values_list("document_type", flat=True)
    )


def _entry_complete(entry, step_number) -> bool:
    has_doc = entry.documents.exists()
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


def _fixed_entries_complete(process, step_number) -> bool:
    entries = {
        e.institute_code: e
        for e in process.institute_entries.filter(step_number=step_number, is_custom=False)
    }
    return all(
        code in entries and _entry_complete(entries[code], step_number)
        for code in codes_for_step(step_number)
    )


def _step_complete(process, step_number, step_row) -> bool:
    if step_number == 1:
        header_ok = bool(process.parcel_id and process.category_id) and not process.duplicate_flagged
        return header_ok and STEP1_REQUIRED_DOCS <= _present_doc_types(process, 1)
    if step_number == 2:
        return bool(step_row.start_date) and _fixed_entries_complete(process, 2)
    if step_number == 3:
        if not _fixed_entries_complete(process, 3):
            return False
        if step_row.out_of_city_flag:
            customs = list(process.institute_entries.filter(step_number=3, is_custom=True))
            return bool(customs) and all(
                e.custom_name and _entry_complete(e, 3) for e in customs
            )
        return True
    if step_number == 4:
        return _fixed_entries_complete(process, 4)
    if step_number == 5:
        prior = process.steps.filter(step_number__lt=5)
        return all(s.status == ProcessStep.Status.COMPLETE for s in prior)
    return False


def _step_has_data(process, step_number, step_row) -> bool:
    if step_number == 1:
        return bool(
            process.parcel_id or process.category_id or process.documents.filter(step_number=1).exists()
        )
    if step_number == 5:
        return False  # Step 5 is derived from the others; it holds no data of its own
    has_entries = process.institute_entries.filter(step_number=step_number).exists()
    has_docs = process.documents.filter(step_number=step_number).exists()
    return bool(has_entries or has_docs or step_row.start_date or step_row.end_date)


def compute_step_status(process, step_number, step_row) -> str:
    """Derive not_started / in_progress / complete for one step (missing is set explicitly)."""
    if _step_complete(process, step_number, step_row):
        return ProcessStep.Status.COMPLETE
    if _step_has_data(process, step_number, step_row):
        return ProcessStep.Status.IN_PROGRESS
    return ProcessStep.Status.NOT_STARTED


def step_status_summary(process) -> dict:
    """Rollup for the process header/list badges (§5.4): per-step status + completed count."""
    steps = {s.step_number: s.status for s in process.steps.all()}
    completed = sum(1 for status in steps.values() if status == ProcessStep.Status.COMPLETE)
    return {"steps": steps, "completed": completed, "total": len(steps)}
