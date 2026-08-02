"""Install the office's letter templates from the repo (§6.6, UC-010).

Templates are no longer uploaded from the running app: the API is read-only, and the active letter
is a reviewed, version-controlled artifact. This command is the supported install path, so a
ministry wording change becomes an edit in the repo plus one command on the office's machine.
"""

from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError

from accounts.models import User
from documents.models import DocumentTemplate
from documents.services import create_template

# Where the .docx files live in the repo. In-repo is the point of "changed in programming" — the
# file that produces a government letter is reviewable and version-controlled.
TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "documents" / "letter_templates"

# Filename → the type it is installed as. Adding a template type means adding one line here.
FILENAMES = {
    DocumentTemplate.TemplateType.ELIGIBILITY_SINGLE: "eligibility_single.docx",
    DocumentTemplate.TemplateType.PROCESS_LIST: "process_list.docx",
    DocumentTemplate.TemplateType.CASE_SUMMARY: "case_summary.docx",
}


class Command(BaseCommand):
    help = "Install/activate the .docx letter templates shipped in the repo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--type",
            choices=list(FILENAMES),
            help="Install only this template type (default: every file present).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Reinstall even when the active template already matches the file on disk.",
        )

    def handle(self, *args, **options):
        actor = User.objects.filter(role=User.Role.ADMIN).order_by("id").first()
        if actor is None:
            raise CommandError("No admin user exists to attribute the install to; run seed_dev.")

        wanted = [options["type"]] if options["type"] else list(FILENAMES)
        installed = 0
        for template_type in wanted:
            path = TEMPLATES_DIR / FILENAMES[template_type]
            if not path.is_file():
                self.stdout.write(self.style.WARNING(f"skip {template_type}: {path} not found"))
                continue

            content = path.read_bytes()
            # Reinstalling an identical file would retire the active template and replace it with a
            # byte-identical copy — churn in an append-only history for no change at all.
            active = DocumentTemplate.objects.filter(
                template_type=template_type, is_active=True
            ).first()
            if active and not options["force"]:
                from documents import filestore

                if active.sha256 == filestore.sha256_hex(content):
                    self.stdout.write(f"unchanged {template_type} ({active.name})")
                    continue

            template = create_template(
                template_type=template_type,
                name=path.stem,
                upload=SimpleUploadedFile(path.name, content),
                actor=actor,
            )
            installed += 1
            self.stdout.write(self.style.SUCCESS(f"installed {template_type} as #{template.id}"))

        self.stdout.write(f"done — {installed} installed")
