"""Keep the store's paths true after the data they were composed from changes (§6.7).

Both names a document carries are derived from the person: the folder from their category, case
code and PID, the download name from their name. Correcting any of those makes the path a lie.

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
from .services import compose_names


def _target(document) -> tuple[str, str, Path]:
    """Where this document *should* live and be called, given the client as they are now.

    Deliberately `compose_names`, not `compose_location`: the latter **claims** a filename on disk,
    which is right for a new document and wrong for one that already has a name to keep.
    """
    return compose_names(
        process=document.process,
        document_type=document.document_type,
        institute_entry=document.institute_entry,
    )


def _keep_number(label: str, old_path: str) -> str:
    """Carry the file's number across the rename, refreshing only the derived label (UC-097).

    The number is what tells two files in one slot apart, so it belongs to the *file* and must
    survive a move — exactly the job the `__<shortid>` did before it (§6.7). Composing the name
    from the label plus that number, rather than reserving a fresh one, is also what keeps
    re-filing **idempotent**: a reservation claims a new number on every call, so running it twice
    would move every document a second time and burn a number doing it.
    """
    return filestore.numbered_name(label, filestore.number_of(old_path))


def _taken(rel: Path, document, claimed: set[str]) -> bool:
    """Whether `rel` is spoken for by anything other than this document — a name another document
    is moving to in this same run, or a file already on disk."""
    return str(rel) != document.file_path and (
        str(rel) in claimed or (settings.DOCUMENTS_ROOT / rel).exists()
    )


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
    # Every name this run has already handed out, so two documents in one slot cannot be sent to
    # the same place. It matters for files stored **before** UC-097: two of them carry different
    # `__<shortid>`s and both parse as "number 1", so both would compose the same new name and the
    # second move would overwrite the first — a citizen's paper, silently gone.
    claimed = {d.file_path for d in documents}
    for document in documents:
        display, label, directory = _target(document)
        # Keep the original number — only the *derived* parts of the name may change. The stored
        # name alone: since UC-060 the download name carries no discriminator to preserve.
        rel = directory / _keep_number(label, document.file_path)
        claimed.discard(document.file_path)
        if _taken(rel, document, claimed):
            # Not `reserve_stored_name`: that probes the filesystem, and this run's moves are all
            # deferred to commit, so nothing is on disk yet and every collision would be handed
            # the same free name. `claimed` is the only record of what this run has promised.
            n = 2
            while _taken(directory / filestore.numbered_name(label, n), document, claimed):
                n += 1
            rel = directory / filestore.numbered_name(label, n)
        claimed.add(str(rel))
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
    # A row whose file is already missing must not turn an otherwise-good save into a 500. This
    # runs `on_commit`, so the rename is committed by the time it fires — raising here would
    # report failure for a change that has in fact been made. The row is the record of where the
    # file belongs (§6.7); it simply goes on pointing at a gap it was already pointing at.
    if not (settings.DOCUMENTS_ROOT / source).exists():
        return
    filestore.move_into_place(source=source, rel_path=rel_path)
    # Never touch a category folder or the staging area — only the person level is disposable.
    if old_dir.is_dir() and old_dir.parent != settings.DOCUMENTS_ROOT and not any(old_dir.iterdir()):
        old_dir.rmdir()
