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
    """Reuse the existing short id so the file stays traceable across the rename (§6.7).

    Falls back to the freshly composed name if the old path carries no `__<shortid>` — a shape
    this codebase never produces, but one a hand-placed file could have. Without the guard the
    whole old path would be spliced in as the "short id", slashes and all, and the rename would
    write outside the folder it was aiming at.
    """
    marker, _, tail = old_path.rpartition("__")
    if not marker or "/" in tail:
        return new_name
    return f"{new_name.rpartition('__')[0]}__{filestore.sanitize(tail.removesuffix('.pdf'), 'x', 40)}.pdf"


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
                lambda s=source, r=rel: _move_and_tidy(source=s, rel_path=r)
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


def _move_and_tidy(*, source: Path, rel_path: Path) -> None:
    """Move the file, then drop the person folder it just left if nothing remains in it.

    Targeted rather than a sweep of the whole store: only one folder can have been emptied, and
    walking every person folder on each re-file would cost more the larger the archive grows.
    A folder still holding a soft-deleted document's file is correctly left alone — that row
    still points at it, and restoring it must not find a hole.
    """
    old_dir = (settings.DOCUMENTS_ROOT / source).parent
    filestore.move_into_place(source=source, rel_path=rel_path)
    # Never touch a category folder or the staging area — only the person level is disposable.
    if old_dir.is_dir() and old_dir.parent != settings.DOCUMENTS_ROOT and not any(old_dir.iterdir()):
        old_dir.rmdir()
