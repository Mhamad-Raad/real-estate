"""Re-file the store under `<CATEGORY>/<CODE>_<PID>/<Sorani label>__<sid>.pdf` (§6.7, UC-060).

Two changes at once, because they touch the same paths:

* the person folder becomes a **case** folder, keyed `<CODE>_<PID>`. A person may hold more than
  one case over time (a re-application after a rejection) and their papers were landing in one
  undifferentiated folder — two `ClientID`s, two `SignedAgreement`s, nothing but a short id to say
  which case each belonged to;
* the machine label (`INST_S4_B`, `RealEstate`) becomes the Sorani name of the issuing body or of
  the paper itself, in both the stored name and the download name, so the archive can be searched
  by hand by people who do not know the codes. The download name also loses its `__<shortid>`.

Written to be **safe and resumable**, like `0004_refile_under_pid_folders`: each document moves in
its own transaction, a file already in place or missing is skipped rather than raising, and
`file_path` is only updated once the bytes are actually at the new location. Re-running is a no-op.
"""

from django.db import migrations


def _rebuild(filestore, document, process, client):
    """This document's new (display, rel) pair, keeping its existing short id."""
    old_name = document.file_path.rsplit("/", 1)[-1]
    # `..._ClientID__bf76170e.pdf` — the short id is the last segment and never changes (§6.7).
    stem, _, tail = old_name.rpartition("__")
    if not stem:
        return None, None
    sid = tail.removesuffix(".pdf")
    category_code = process.category.code if process.category_id else "NA"
    label = filestore.document_label(document.document_type, document.institute_entry)
    display = filestore.compose_display_name(
        unique_code=process.unique_code,
        category_code=category_code,
        # The spouse's papers are named for the spouse; rebuilt here rather than imported, because
        # `services.subject_name` is live code and this migration must stay pinned to what it saw.
        person_name=(
            client.spouse_name
            if document.document_type == "SpouseID" and client.spouse_name
            else client.full_name
        ),
        label=label,
    )
    rel = filestore.relative_path(
        category_code=category_code,
        unique_code=process.unique_code,
        pid=client.pid,
        stored_filename=filestore.compose_stored_name(label=label, sid=sid),
    )
    return display, rel


def refile(apps, schema_editor):
    from django.conf import settings

    from documents import filestore

    Document = apps.get_model("documents", "Document")
    root = settings.DOCUMENTS_ROOT

    # `all_objects` equivalent: the historical model has a plain manager, so soft-deleted rows are
    # included — their files are on disk too and would be orphaned by a live-rows-only sweep.
    for document in Document.objects.select_related(
        "process__client", "process__category", "institute_entry"
    ):
        if not document.file_path:
            continue
        process = document.process
        display, rel = _rebuild(filestore, document, process, process.client)
        if rel is None:
            continue
        if str(rel) == document.file_path and display == document.display_filename:
            continue

        # The download name lives only in the DB, so it is corrected even when nothing moves.
        document.display_filename = display
        if str(rel) == document.file_path:
            document.save(update_fields=["display_filename"])
            continue

        source, dest = root / document.file_path, root / rel
        if dest.exists():  # already moved by an earlier run
            document.file_path = str(rel)
            document.save(update_fields=["file_path", "display_filename"])
            continue
        if not source.exists():  # nothing to move; leave the row pointing where it did
            document.save(update_fields=["display_filename"])
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)
        source.replace(dest)
        document.file_path = str(rel)
        document.save(update_fields=["file_path", "display_filename"])

    _drop_empty_case_folders(root)


def _drop_empty_case_folders(root):
    """Tidy the folders the move emptied. Only the case level — a category folder stays."""
    if not root.is_dir():
        return
    for category in root.iterdir():
        # `_staging`, `_generated` and `_templates` are not category folders (§6.7).
        if not category.is_dir() or category.name.startswith("_"):
            continue
        for case in category.iterdir():
            if case.is_dir() and not any(case.iterdir()):
                case.rmdir()


def noop(apps, schema_editor):
    """No reverse: the machine label cannot be recovered once the Sorani name has replaced it,
    and the DB pointer is authoritative either way (§6.7)."""


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0005_add_process_codes_type"),
        # The case code is what the new folder is keyed on.
        ("processes", "0009_add_unique_code"),
    ]

    operations = [migrations.RunPython(refile, noop)]
