"""Measure the card reader against cards whose true values are known (UC-126).

    python manage.py ocr_bench /samples/truth.csv
    python manage.py ocr_bench /samples/truth.csv --only S1,P2 --json /tmp/run.json

The manifest is a CSV beside the samples: `card, kind, front, back, pid, full_name,
mother_full_name, date_of_birth, note`, with file paths relative to the CSV. **The samples and the
manifest are real people's cards: they live outside the repository and are never committed.**

Each card goes through exactly what an upload goes through — each side converted with
`normalise_to_pdf`, both merged into one PDF, that PDF handed to `read_card` — so a number here
describes the office's reading, not a friendlier path the bench invented.
"""

import csv
import json
import tempfile
import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from documents import filestore
from documents.services import normalise_to_pdf
from ocr.bench import FIELDS, CardResult, score_field, summarise
from ocr.reader import read_card


class Command(BaseCommand):
    help = "Score the ID-card reader against a manifest of cards with known values."

    def add_arguments(self, parser):
        parser.add_argument("manifest", help="CSV of cards and their true values.")
        parser.add_argument("--only", default="", help="Comma-separated card ids to run.")
        parser.add_argument("--json", default="", help="Also write every drafted value here.")

    def handle(self, *args, **options):
        manifest = Path(options["manifest"])
        if not manifest.is_file():
            raise CommandError(f"No manifest at {manifest}")
        only = {c.strip() for c in options["only"].split(",") if c.strip()}
        rows = [r for r in csv.DictReader(manifest.open(encoding="utf-8")) if not only or r["card"] in only]

        results = []
        for row in rows:
            result = self._run(manifest.parent, row)
            results.append(result)
            self.stdout.write(self._line(result))

        self.stdout.write("")
        for kind in sorted({r.kind for r in results}):
            self._report(kind, [r for r in results if r.kind == kind])
        self._report("all", results)

        if options["json"]:
            Path(options["json"]).write_text(
                json.dumps(
                    [
                        {
                            "card": r.card,
                            "kind": r.kind,
                            "seconds": r.seconds,
                            "error": r.error,
                            "drafted": r.drafted,
                            "outcomes": {k: v.outcome for k, v in r.scores.items()},
                        }
                        for r in results
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

    def _run(self, root: Path, row: dict) -> CardResult:
        result = CardResult(card=row["card"], kind=row["kind"], seconds=0.0)
        try:
            # The upload path, verbatim: each side normalised, both merged into one file.
            content = normalise_to_pdf((root / row["front"]).read_bytes(), field="front")
            if row.get("back"):
                back = normalise_to_pdf((root / row["back"]).read_bytes(), field="back")
                content = filestore.merge_pdfs([content, back])
            with tempfile.NamedTemporaryFile(suffix=".pdf") as staged:
                staged.write(content)
                staged.flush()
                started = time.monotonic()
                draft = read_card(Path(staged.name)).as_dict()["fields"]
                result.seconds = round(time.monotonic() - started, 1)
        except Exception as exc:  # a card that crashes the reader is a result, not a stop
            result.error = f"{type(exc).__name__}: {exc}"
            draft = {}
        for name in FIELDS:
            result.scores[name] = score_field(name, row.get(name, ""), draft.get(name, {}))
            result.drafted[name] = (draft.get(name) or {}).get("value", "")
        return result

    def _line(self, r: CardResult) -> str:
        marks = {"correct": "✓", "empty": "·", "wrong": "✗", "n/a": " "}
        cells = " ".join(f"{name[:6]}:{marks[r.scores[name].outcome]}" for name in FIELDS)
        tail = f"  ERROR {r.error}" if r.error else ""
        return f"{r.card:4} {r.kind:5} {r.seconds:5.1f}s  {cells}{tail}"

    def _report(self, label: str, results: list[CardResult]) -> None:
        if not results:
            return
        seconds = sorted(r.seconds for r in results)
        self.stdout.write(
            f"== {label}: {len(results)} cards, median {seconds[len(seconds) // 2]}s, max {seconds[-1]}s"
        )
        for name, s in summarise(results).items():
            self.stdout.write(
                f"   {name:17} correct {s['correct']:>2}/{s['cards']:<2}  empty {s['empty']:>2}  "
                f"wrong {s['wrong']:>2}  similarity {s['mean_similarity']:.2f}"
                + (f"  VERIFIED-BUT-WRONG {s['verified_but_wrong']}" if s["verified_but_wrong"] else "")
            )
