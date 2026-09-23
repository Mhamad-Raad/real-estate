"""Scoring for the OCR accuracy bench (UC-126).

Pure functions only: the management command `ocr_bench` does the file handling and calls the real
reader, and this module decides how right each drafted field was. Kept apart so the scoring rules
are tested on their own, and so a change to the reader cannot quietly change how it is judged.

The rule that matters most is the three-way outcome. A field is **correct**, **empty** or
**wrong** — and those are not two shades of the same failure. An empty box asks the lawyer to
type; a wrong one invites them to accept it (§6.5). So the bench reports wrong fields separately,
and a change that trades empties for wrongs is a regression even when "correct" goes up.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .text import normalise_name, similarity

FIELDS = ("pid", "full_name", "mother_full_name", "date_of_birth")
NAME_FIELDS = ("full_name", "mother_full_name")


@dataclass
class FieldScore:
    outcome: str  # "correct" | "empty" | "wrong" | "n/a"
    similarity: float = 0.0
    # A wrong value the reader marked as verified — the worst case, a confident misread.
    verified_but_wrong: bool = False


def score_field(name: str, expected: str, drafted: dict) -> FieldScore:
    """Judge one drafted field against the value printed on the card."""
    if not expected:
        return FieldScore("n/a")
    value = (drafted or {}).get("value", "") or ""
    verified = bool((drafted or {}).get("verified"))
    if not value.strip():
        return FieldScore("empty")
    if name in NAME_FIELDS:
        a, b = normalise_name(value), normalise_name(expected)
        # A name split or joined differently ("عبد الزهرة" / "عبدالزهرة") is still the same name.
        same = a == b or a.replace(" ", "") == b.replace(" ", "")
        return FieldScore("correct" if same else "wrong", similarity(a, b))
    same = value.strip() == expected.strip()
    return FieldScore(
        "correct" if same else "wrong",
        1.0 if same else similarity(value.strip(), expected.strip()),
        verified_but_wrong=verified and not same,
    )


@dataclass
class CardResult:
    card: str
    kind: str
    seconds: float
    scores: dict[str, FieldScore] = field(default_factory=dict)
    drafted: dict[str, str] = field(default_factory=dict)
    error: str = ""


def summarise(results: list[CardResult]) -> dict[str, dict[str, float]]:
    """Per field: how many cards were scored, and the share correct / empty / wrong."""
    summary: dict[str, dict[str, float]] = {}
    for name in FIELDS:
        scored = [r.scores[name] for r in results if name in r.scores and r.scores[name].outcome != "n/a"]
        total = len(scored)
        counts = {k: sum(1 for s in scored if s.outcome == k) for k in ("correct", "empty", "wrong")}
        summary[name] = {
            "cards": total,
            **counts,
            "mean_similarity": round(sum(s.similarity for s in scored) / total, 3) if total else 0.0,
            "verified_but_wrong": sum(1 for s in scored if s.verified_but_wrong),
        }
    return summary
