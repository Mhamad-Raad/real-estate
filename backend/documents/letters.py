"""Context builders for the generated letters (§6.6, §6.8).

Pure functions: a process (or several) in, a plain dict out. This dict is the **contract** the
`.docx` templates bind to — when the office supplies its own Word files, they use these same
names and no code changes.

Every number is rendered in Arabic-Indic digits, matching the paper forms the office uses.
"""

from datetime import date

ARABIC_INDIC = "٠١٢٣٤٥٦٧٨٩"


def to_arabic_indic(value) -> str:
    """1990 → ١٩٩٠. Idempotent: Arabic-Indic digits map to themselves."""
    return "".join(ARABIC_INDIC[int(ch)] if ch.isdigit() else ch for ch in str(value))


def _year(value: date | None) -> str:
    return to_arabic_indic(value.year) if value else ""


def row_for_process(process, number: int) -> dict:
    """One table row: the beneficiary, plus the spouse columns beside them.

    An unmarried beneficiary yields empty spouse values on purpose — the paper form keeps the
    spouse cells present but blank rather than dropping them.
    """
    client = process.client
    married = client.is_married
    return {
        "n": to_arabic_indic(number),
        "full_name": client.full_name,
        "year": _year(client.date_of_birth),
        "mother_name": client.mother_full_name,
        "spouse_name": client.spouse_name if married else "",
        "spouse_year": _year(client.spouse_date_of_birth) if married else "",
        "spouse_mother_name": client.spouse_mother_full_name if married else "",
    }


def _context(rows: list[dict]) -> dict:
    return {
        "rows": rows,
        "count": to_arabic_indic(len(rows)),
        # The list letter's body names the range it covers: "begins with X … ends with Y".
        "first_name": rows[0]["full_name"] if rows else "",
        "last_name": rows[-1]["full_name"] if rows else "",
    }


def eligibility_context(process) -> dict:
    """The single-beneficiary letter — the same shape as the list, with exactly one row."""
    return _context([row_for_process(process, 1)])


def process_list_context(processes) -> dict:
    """The bulk letter — one numbered row per selected process, in the order given."""
    return _context([row_for_process(p, i) for i, p in enumerate(processes, start=1)])


# The office's own banding for the code list: odd rows keep the shade the form already had, even
# rows take a lighter one so a long list is easy to read across (UC-057, follow-up). Driven from
# the context rather than the template because docxtpl repeats a single row — the only way to vary
# it per row is to let the row ask what colour it is.
CODE_ROW_SHADE_ODD = "d9e7f9"
CODE_ROW_SHADE_EVEN = "eff5fd"


def process_codes_context(processes) -> dict:
    """The code list (§6.8, UC-057) — one row per selected case: number, name, code, land number.

    A separate contract from the eligibility/list letters on purpose: the office's form has its own
    columns, and folding them into `row_for_process` would make one dict serve two documents that
    are free to diverge. The `تێبینی` (notes) column is left for the office to write on by hand.
    """
    return {
        "rows": [
            {
                "n": to_arabic_indic(number),
                "full_name": process.client.full_name,
                "code": process.unique_code,
                "land_id": process.land_id,
                "shade": CODE_ROW_SHADE_ODD if number % 2 else CODE_ROW_SHADE_EVEN,
            }
            for number, process in enumerate(processes, start=1)
        ]
    }
