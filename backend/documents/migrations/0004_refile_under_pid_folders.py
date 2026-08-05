"""Move the document store to `<CATEGORY>/<pid>/<institute>_<type>__<sid>.pdf` (§6.7).

Two changes at once, because they touch the same paths:

* the person folder is keyed by the **PID** instead of `<client_id>_<pid>`, so one human has one
  folder even if their record was re-entered;
* the on-disk filename drops the category and the person, which the folders above already carry.
  `display_filename` is untouched — downloads keep the long self-describing name.

Written to be **safe and resumable**: each document moves in its own transaction, a file that is
already in place or missing is skipped rather than raising, and `file_path` is only updated once
the bytes are actually at the new location. A half-finished run can simply be re-run.
"""

from pathlib import Path

from django.db import migrations


def _new_path(filestore, document, client, category_code):
    """Rebuild this document's path under the scheme **this** migration introduced, keeping its
    short id.

    The layout is spelled out here rather than composed through `filestore`. That module tracks
    the store as it is *today* — UC-060 has since moved it on again, to case folders and Sorani
    labels — and a migration that follows it would stop reproducing the state the next migration
    expects to find. A historical migration has to stay pinned to the shape it was written for.
    """
    old_name = document.file_path.rsplit("/", 1)[-1]
    # `..._ClientID__bf76170e.pdf` — the short id is the last segment and never changes (§6.7).
    stem, _, tail = old_name.rpartition("__")
    if not stem:
        return None
    sid = tail.removesuffix(".pdf")
    institute = stem.split("_")[1] if len(stem.split("_")) > 1 else "General"
    return (
        Path(filestore.sanitize(category_code, "NA", 10))
        / filestore.sanitize(client.pid, "NA", 40)
        / (
            f"{filestore.sanitize(institute, 'General')}"
            f"_{filestore.sanitize(document.document_type, 'Document')}__{sid}.pdf"
        )
    )


def refile(apps, schema_editor):
    from django.conf import settings

    from documents import filestore

    Document = apps.get_model("documents", "Document")
    root = settings.DOCUMENTS_ROOT

    # `all_objects` equivalent: the historical model has a plain manager, so soft-deleted rows are
    # included — their files are on disk too and would be orphaned by a live-rows-only sweep.
    for document in Document.objects.select_related("process__client", "process__category"):
        if not document.file_path:
            continue
        client = document.process.client
        category = document.process.category
        rel = _new_path(filestore, document, client, category.code if category else "NA")
        if rel is None or str(rel) == document.file_path:
            continue

        source, dest = root / document.file_path, root / rel
        if dest.exists():  # already moved by an earlier run
            document.file_path = str(rel)
            document.save(update_fields=["file_path"])
            continue
        if not source.exists():  # nothing to move; leave the row pointing where it did
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)
        source.replace(dest)
        document.file_path = str(rel)
        document.save(update_fields=["file_path"])


def noop(apps, schema_editor):
    """No reverse: the old path cannot be rebuilt once the person's name has left the filename,
    and the DB pointer is authoritative either way (§6.7)."""


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0003_alter_documenttemplate_template_type_and_more"),
        ("clients", "0004_client_spouse_pid"),
    ]

    operations = [migrations.RunPython(refile, noop)]
