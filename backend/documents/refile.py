"""Keep the store's paths true after the data they were composed from changes (§6.7).

Both names a document carries are derived from the person: the folder from their category and
PID, the download name from their name. Correcting any of those makes the stored path a lie.

Shortening the on-disk name (It.5) removed most of this problem — the person's name is no longer
part of it, so a name correction now only rewrites `display_filename` in the database and never
touches the filesystem. Two changes still move real files:

* **a category change** — the top-level folder is the category letter;
* **a PID correction** — the person folder is keyed by the PID.

Both are rare and both are audited. The `__<shortid>` suffix never changes, so a file stays
traceable across any number of re-filings.
"""

from pathlib import Path

from django.conf import settings
from django.db import transaction

from common.models import ActivityLog
from common.services import record_activity

from . import filestore
from .models import Document
from .services import compose_location


def _target(document) -> tuple[str, Path]:
    """Where this document *should* live and be called, given the client as they are now."""
    return compose_location(
        process=document.process,
        document_type=document.document_type,
        institute_entry=document.institute_entry,
    )


def _keep_short_id(new_name: str, old_path: str) -> str:
    """Reuse the existing short id so the file stays traceable across the rename (§6.7)."""
    old_sid = old_path.rsplit("__", 1)[-1].removesuffix(".pdf")
    stem, _, _ = new_name.rpartition("__")
    return f"{stem}__{old_sid}.pdf"


@transaction.atomic
def refile_client_documents(client, *, actor=None, request=None) -> list[int]:
    """Re-file every document of a client whose category, PID or name has changed.

    Returns the ids actually re-filed. A document already in the right place is skipped, so this
    is cheap to call on every client edit and safe to run twice.
    """
    moved = []
    documents = (
        Document.objects.filter(process__client=client)
        .select_related("process__client", "process__category", "institute_entry")
    )
    for document in documents:
        display, rel = _target(document)
        # Keep the original short id — only the *derived* parts of the name may change.
        rel = rel.parent / _keep_short_id(rel.name, document.file_path)
        display = _keep_short_id(display, document.file_path)
        if str(rel) == document.file_path and display == document.display_filename:
            continue

        before = {"file_path": document.file_path, "display_filename": document.display_filename}
        needs_move = str(rel) != document.file_path
        source = Path(document.file_path)
        document.file_path = str(rel)
        document.display_filename = display
        document.save(update_fields=["file_path", "display_filename", "updated_at"])
        if needs_move:
            # On commit, for the same reason filing a scan is: a filesystem move cannot be rolled
            # back with the transaction, so it must not happen until the rows are safe.
            transaction.on_commit(
                lambda s=source, r=rel: filestore.move_into_place(source=s, rel_path=r)
            )
        record_activity(
            actor=actor,
            action=ActivityLog.Action.UPDATE,
            entity_type="Document",
            entity_id=document.id,
            before=before,
            after={"file_path": str(rel), "display_filename": display, "reason": "re-filed"},
            request=request,
        )
        moved.append(document.id)
    return moved


def prune_empty_person_dirs() -> int:
    """Remove person folders left empty by a re-filing. Categories are kept — they are fixed."""
    root = settings.DOCUMENTS_ROOT
    removed = 0
    for category in root.iterdir() if root.exists() else []:
        if not category.is_dir() or category.name.startswith("_"):
            continue
        for person in category.iterdir():
            if person.is_dir() and not any(person.iterdir()):
                person.rmdir()
                removed += 1
    return removed
