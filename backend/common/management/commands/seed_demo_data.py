"""Seed clearly-marked demo cases so the app can be explored without touching real records.

**Dev only.** Every demo beneficiary gets a `DEMO-` PID, which a real 12-digit government ID can
never collide with — so demo records are obvious in the UI, sort together in search, and live in
their own `<CATEGORY>/DEMO-xxxx/` folders on disk. That marker is what makes `--purge` safe and
what keeps pilot findings (It.7) from ever being confused with data I generated.

Everything is written through the domain services, so the demo data carries the same audit trail,
status computation and duplicate checks as data typed in by hand — seeding through raw inserts
would produce cases the app itself considers impossible.
"""

from datetime import date, timedelta
from io import BytesIO

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from catalog.models import Category
from clients.models import Client
from clients.services import create_client
from documents.models import Document
from documents.services import create_document
from processes.models import Process, ProcessInstituteEntry, ProcessStep
from processes.services import advance_step, complete_process, recompute_step
from processes.services import create_process

# A real national ID is 12 digits, so this prefix cannot collide with one (§3.7).
DEMO_PID_PREFIX = "DEMO-"

CATEGORIES = [("A", "Category A"), ("B", "Category B"), ("C", "Category C"), ("G", "General")]


def demo_pdf(title: str, subtitle: str) -> bytes:
    """A one-page PDF with visible text, so previews and the compiled export show something.

    Blank pages would technically satisfy every check while making the Step-5 export and the RTL
    print validation impossible to judge by eye — which is most of what this data is for.
    """
    from PIL import Image, ImageDraw

    from documents import filestore

    # A4 at 150 dpi — readable on screen without making the demo store needlessly large.
    page = Image.new("RGB", (1240, 1754), (255, 255, 255))
    draw = ImageDraw.Draw(page)
    draw.rectangle([60, 60, 1180, 1694], outline=(30, 30, 30), width=4)
    draw.text((120, 140), "DEMO DOCUMENT - NOT A REAL RECORD", fill=(180, 30, 30))
    draw.text((120, 220), title, fill=(10, 10, 10))
    draw.text((120, 280), subtitle, fill=(60, 60, 60))
    buffer = BytesIO()
    page.save(buffer, format="JPEG", quality=85)
    return filestore.image_to_pdf(buffer.getvalue())


class Command(BaseCommand):
    help = "Create (or purge) clearly-marked DEMO- cases for exploring the app. Dev only."

    def add_arguments(self, parser):
        parser.add_argument(
            "--purge", action="store_true", help="Soft-delete every DEMO- record and stop."
        )
        parser.add_argument(
            "--reset", action="store_true", help="Purge existing demo data, then seed it again."
        )

    def handle(self, *args, **options):
        if options["purge"]:
            self._purge()
            return

        existing = Client.objects.filter(pid__startswith=DEMO_PID_PREFIX).count()
        if existing and not options["reset"]:
            self.stdout.write(
                self.style.WARNING(
                    f"{existing} demo beneficiaries already exist — nothing done. "
                    "Use --reset to rebuild them, or --purge to remove them."
                )
            )
            return
        if options["reset"]:
            self._purge()

        self.admin = User.objects.filter(role=User.Role.ADMIN).order_by("id").first()
        self.lawyer = (
            User.objects.filter(role=User.Role.LAWYER, is_active=True).order_by("id").first()
        )
        if not self.admin or not self.lawyer:
            self.stdout.write(self.style.ERROR("Run `manage.py seed_dev` first — no users found."))
            return

        self._categories()
        self._seed()

    # ------------------------------------------------------------------ purge

    def _purge(self):
        """Soft-delete demo records only. Nothing is hard-deleted — the project never does (§11).

        **Deliberate dev-only deviation:** this bulk-updates `is_deleted` and so writes no DELETE
        audit rows, which the append-only-audit invariant would otherwise require (§11). It is
        acceptable *only* because these records describe nobody — auditing the removal of data I
        invented would bury real history in noise. **Never copy this pattern into app code:** a
        bulk soft-delete losing its audit row was a real defect found in It.3.
        """
        clients = Client.all_objects.filter(pid__startswith=DEMO_PID_PREFIX)
        processes = Process.all_objects.filter(client__in=clients)
        counts = {
            "documents": Document.all_objects.filter(process__in=processes, is_deleted=False).update(
                is_deleted=True, deleted_at=timezone.now()
            ),
            "institute entries": ProcessInstituteEntry.all_objects.filter(
                process__in=processes, is_deleted=False
            ).update(is_deleted=True, deleted_at=timezone.now()),
            "steps": ProcessStep.all_objects.filter(
                process__in=processes, is_deleted=False
            ).update(is_deleted=True, deleted_at=timezone.now()),
            "processes": processes.filter(is_deleted=False).update(
                is_deleted=True, deleted_at=timezone.now()
            ),
            "beneficiaries": clients.filter(is_deleted=False).update(
                is_deleted=True, deleted_at=timezone.now()
            ),
        }
        for label, n in counts.items():
            self.stdout.write(f"  - soft-deleted {n} {label}")
        self.stdout.write(self.style.SUCCESS("Demo data purged."))

    # ------------------------------------------------------------- scaffolding

    def _categories(self):
        for code, name in CATEGORIES:
            _, created = Category.objects.get_or_create(code=code, defaults={"name": name})
            if created:
                self.stdout.write(f"  + category {code}")
        self.cats = {c.code: c for c in Category.objects.all()}

    def _client(self, n, name, mother, born, *, married=None):
        """One demo beneficiary. `married` is the spouse tuple, or None for a single person."""
        data = {
            "full_name": name,
            "pid": f"{DEMO_PID_PREFIX}{n:04d}",
            "mother_full_name": mother,
            "date_of_birth": born,
            "category": self.cats["A"],
        }
        if married:
            spouse_name, spouse_born, spouse_mother = married
            data |= {
                "marital_status": Client.MaritalStatus.MARRIED,
                "spouse_name": spouse_name,
                "spouse_date_of_birth": spouse_born,
                "spouse_mother_full_name": spouse_mother,
            }
        return create_client(data=data, actor=self.admin)

    def _case(self, client, *, category="A", land_id="", address=""):
        process = create_process(
            client=client, assigned_lawyer=self.lawyer, actor=self.admin, category=self.cats[category]
        )
        if land_id:
            process.land_id = land_id
            process.land_address = address
            process.save(update_fields=["land_id", "land_address", "updated_at"])
        return process

    def _doc(self, process, step, doc_type, title, *, entry=None):
        return create_document(
            process=process,
            step_number=step,
            document_type=doc_type,
            input_source=Document.InputSource.IMPORTED,
            content=demo_pdf(title, process.client.full_name),
            actor=self.lawyer,
            institute_entry=entry,
            original_filename=f"demo_{doc_type}.pdf",
        )

    def _step1_papers(self, process):
        self._doc(process, 1, "ClientID", "National ID card")
        self._doc(process, 1, "RealEstate", "Real-estate papers")
        self._doc(process, 1, "SignedAgreement", "Signed agreement")
        if process.client.is_married:
            self._doc(process, 1, "SpouseID", "Spouse national ID card")

    def _institutes(self, process, step, codes, *, decided=True, dated=True, custom=None):
        """Fixed institute rows for a step, each finished to that step's own rule (§3.6)."""
        for code in codes:
            entry = ProcessInstituteEntry.objects.create(
                process=process,
                step_number=step,
                institute_code=code,
                assigned_lawyer=self.lawyer,
                approval_status=(
                    ProcessInstituteEntry.ApprovalStatus.APPROVED
                    if decided
                    else ProcessInstituteEntry.ApprovalStatus.PENDING
                ),
                approval_date=date.today() - timedelta(days=7) if dated else None,
            )
            self._doc(process, step, "InstituteDoc", f"Institute {code} approval", entry=entry)
        if custom:
            entry = ProcessInstituteEntry.objects.create(
                process=process,
                step_number=step,
                is_custom=True,
                custom_name=custom,
                assigned_lawyer=self.lawyer,
                approval_status=ProcessInstituteEntry.ApprovalStatus.APPROVED,
                approval_date=date.today() - timedelta(days=5),
            )
            self._doc(process, step, "InstituteDoc", f"{custom} approval", entry=entry)

    def _open_to(self, process, step):
        """Unlock steps up to `step` the way the UI does — one audited advance at a time."""
        while process.current_step < step:
            process = advance_step(process=process, actor=self.lawyer, expected_version=process.version)
        return process

    def _start_date(self, process, step, days_ago):
        row = process.steps.get(step_number=step)
        row.start_date = date.today() - timedelta(days=days_ago)
        row.save(update_fields=["start_date", "updated_at"])

    # -------------------------------------------------------------------- seed

    @transaction.atomic
    def _seed(self):
        s2, s3, s4 = ["INST_S2_A"], ["INST_S3_A", "INST_S3_B", "INST_S3_C"], [
            "INST_S4_A",
            "INST_S4_B",
        ]

        # 1 — a case just opened: nothing filed yet, so Step 1 shows every requirement missing.
        c = self._client(1, "کاروان ئەحمەد مستەفا", "گوڵناز ئەحمەد", date(1988, 3, 14))
        self._case(c)

        # 2 — Step 1 complete and nothing beyond it: the state an eligibility letter prints from.
        c = self._client(2, "شیلان عومەر ڕەشید", "پەروین قادر", date(1995, 7, 2))
        p = self._case(c, land_id="LND-2001", address="Erbil — Zone 4, plot 21")
        self._step1_papers(p)

        # 3 — married, working through Step 2.
        c = self._client(
            3, "ئارام سەلام حەمە", "نەسرین حەسەن", date(1983, 11, 9),
            married=("ڕۆژان مەحمود ساڵح", date(1986, 5, 20), "شەونم عەلی"),
        )
        p = self._case(c, land_id="LND-2002", address="Erbil — Zone 7, plot 4")
        self._step1_papers(p)
        p = self._open_to(p, 2)
        self._start_date(p, 2, 30)
        self._institutes(p, 2, s2)

        # 4 — at Step 3 with an out-of-city row, the branch that only Step 3 has (§3.6).
        c = self._client(
            4, "نەورۆز جەلال ئیبراهیم", "سۆزان ڕەسوڵ", date(1979, 1, 25),
            married=("بەیان ئەنوەر تۆفیق", date(1981, 9, 12), "هێڤی سەعید"),
        )
        p = self._case(c, land_id="LND-2003", address="Duhok — Zone 2, plot 88")
        self._step1_papers(p)
        p = self._open_to(p, 3)
        self._start_date(p, 2, 60)
        self._institutes(p, 2, s2)
        step3 = p.steps.get(step_number=3)
        step3.out_of_city_flag = True
        step3.save(update_fields=["out_of_city_flag", "updated_at"])
        self._institutes(p, 3, s3, custom="Sulaymaniyah — out-of-city office")

        # 5 — everything done up to Step 5: the case to test the compiled export on.
        c = self._client(5, "هێمن ڕەئوف قادر", "ئاواز مەجید", date(1990, 6, 30))
        p = self._case(c, land_id="LND-2004", address="Erbil — Zone 1, plot 12")
        self._step1_papers(p)
        p = self._open_to(p, 5)
        self._start_date(p, 2, 90)
        self._institutes(p, 2, s2)
        self._institutes(p, 3, s3)
        self._institutes(p, 4, s4)

        # 6 — a finished allocation, so completed-state screens and reports have something in them.
        c = self._client(
            6, "دلێر شێرکۆ ئەمین", "بەهار ئیسماعیل", date(1975, 2, 8),
            married=("چنار ئازاد کەریم", date(1978, 4, 17), "نازدار وەلی"),
        )
        p = self._case(c, land_id="LND-2005", address="Erbil — Zone 9, plot 7")
        self._step1_papers(p)
        p = self._open_to(p, 5)
        self._start_date(p, 2, 200)
        self._institutes(p, 2, s2)
        self._institutes(p, 3, s3)
        self._institutes(p, 4, s4)
        for n in (1, 2, 3, 4):
            recompute_step(p, n)
        p.refresh_from_db()
        complete_process(process=p, actor=self.admin, expected_version=p.version)

        # 7 — a rejected case, which the "no land twice" rule deliberately lets a client re-apply after.
        c = self._client(7, "ژیان مەحمود عەلی", "شنە فەرهاد", date(1992, 12, 1))
        p = self._case(c, land_id="LND-2006", address="Erbil — Zone 3, plot 55")
        self._step1_papers(p)
        p.overall_status = Process.OverallStatus.REJECTED
        p.lawyer_notes = "Demo: rejected — the applicant already holds an allocation elsewhere."
        p.save(update_fields=["overall_status", "lawyer_notes", "updated_at"])

        # Statuses are derived, never typed in — recompute every step exactly as the app does.
        for process in Process.objects.filter(client__pid__startswith=DEMO_PID_PREFIX):
            for n in (1, 2, 3, 4, 5):
                recompute_step(process, n)

        self._report()

    def _report(self):
        self.stdout.write(self.style.SUCCESS("\nDemo data seeded:"))
        for p in (
            Process.objects.filter(client__pid__startswith=DEMO_PID_PREFIX)
            .select_related("client")
            .order_by("id")
        ):
            steps = " ".join(
                f"{s.step_number}:{s.status[:4]}" for s in p.steps.all().order_by("step_number")
            )
            self.stdout.write(
                f"  #{p.id} {p.client.pid} {p.client.full_name} — "
                f"step {p.current_step}, {p.overall_status}, {p.documents.count()} docs [{steps}]"
            )
        self.stdout.write(
            "\nAll demo beneficiaries carry a DEMO- national ID. "
            "Remove them at any time with:  manage.py seed_demo_data --purge\n"
        )
