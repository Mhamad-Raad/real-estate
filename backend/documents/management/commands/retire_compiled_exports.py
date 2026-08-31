"""Remove the compiled case files the app itself produced before UC-118.

Until then every closed case kept its export — the cover sheet plus every paper on the case,
merged again — as a `Document` in the case folder, so a finished case cost roughly twice its
papers on disk. The export is now a one-read job file that can be produced again in seconds, so
the stored copies buy nothing.

**Only system-made rows go.** A `CompiledCase` the office scanned through the backlog door
(§5.9, UC-114) is the only copy of that paper case; `supersede_generated_documents` filters on
`input_source` and this command never reaches one.

Deliberately a command and not a data migration: it removes files from the office's archive, so
they run it when they choose, after a backup, and can see first what it would remove.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.document_types import COMPILED_CASE

from ...models import Document
from ...services import supersede_generated_documents


class Command(BaseCommand):
    help = "Retire the compiled case exports the app filed on cases before UC-118 (files and rows)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Remove them. Without it the command only reports what it would remove.",
        )

    def handle(self, *args, **options):
        exports = Document.objects.filter(
            document_type=COMPILED_CASE, input_source=Document.InputSource.SYSTEM_GENERATED
        ).select_related("process")
        found = exports.count()
        if not found:
            self.stdout.write(self.style.SUCCESS("Nothing to do — no compiled export is stored on any case."))
            return

        root = Path(settings.DOCUMENTS_ROOT)
        # Measured from disk, not `size_bytes`: a file the office already removed by hand frees nothing.
        on_disk = [root / d.file_path for d in exports]
        total = sum(p.stat().st_size for p in on_disk if p.is_file())
        summary = f"{found} compiled export(s) on {exports.values('process').distinct().count()} case(s), {total / 1_048_576:.1f} MB on disk."
        if not options["apply"]:
            self.stdout.write(f"{summary} Re-run with --apply to remove them.")
            return

        retired = 0
        for process_id in sorted({d.process_id for d in exports}):
            process = next(d.process for d in exports if d.process_id == process_id)
            with transaction.atomic():
                # The same retirement a recompile used to do — row soft-deleted, audited with
                # `file_removed`, PDF unlinked — so the trail reads the same for both.
                retired += supersede_generated_documents(
                    process=process,
                    document_type=COMPILED_CASE,
                    actor=None,
                    reason="retired by retire_compiled_exports (UC-118)",
                )
        self.stdout.write(self.style.SUCCESS(f"Retired {retired} compiled export(s); {summary}"))
