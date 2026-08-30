"""Record how many pages each stored PDF holds, and backfill what is already filed (UC-083).

An ID card is deliberately one document carrying both sides, so counting *rows* told the office a
complete card was "1 of 2 files". The slot needs pages, and reading every PDF on every case load
is not an option, so the number is stored.
"""

from pathlib import Path

from django.conf import settings
from django.db import migrations, models


def backfill_page_counts(apps, schema_editor):
    """Count the pages of every document already on disk.

    Soft-deleted rows are counted too — one is still restorable, and restoring it with a page
    count of 0 would put the wrong number back on the screen. A historical model carries no custom
    manager, so `objects` here is the plain unfiltered one, which is exactly what that needs.

    A file that is missing or unreadable is left at 0 rather than failing the migration: this runs
    on the office's live database during an upgrade, and a single bad scan from before the
    readability check must not be able to block it.

    Streamed in batches rather than gathered into one list: the office is sized for tens of
    thousands of cases, and this opens a file per row — holding every instance in memory while
    doing so is the kind of upgrade that dies halfway on their hardware.
    """
    from pypdf import PdfReader

    Document = apps.get_model("documents", "Document")
    root = Path(settings.DOCUMENTS_ROOT)
    BATCH = 200
    batch = []

    def flush():
        if batch:
            Document.objects.bulk_update(batch, ["page_count"])
            batch.clear()

    for document in Document.objects.all().only("id", "file_path").iterator(chunk_size=BATCH):
        path = root / document.file_path
        if not path.is_file():
            continue
        try:
            document.page_count = len(PdfReader(str(path)).pages)
        except Exception:
            continue
        batch.append(document)
        if len(batch) >= BATCH:
            flush()
    flush()


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0007_alter_documenttemplate_template_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="page_count",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        # Reverse is a no-op: dropping the column takes the values with it.
        migrations.RunPython(backfill_page_counts, migrations.RunPython.noop),
    ]
