"""The ONE definition of the Step 2–4 institutes (§3.4).

Backend validates `ProcessInstituteEntry.institute_code` against this; the frontend fetches it
read-only via GET /api/v1/institutes/ and never hard-codes it. Display names are i18n keys, so
the machine `code` is stable in the DB while ckb/ar/en labels come from the translation files.
"""

# The codes are opaque and permanent — they are stored on every entry row, so renaming the body
# behind one is a translation change, never a data migration. See §3.4 for what each one is.
# (code, i18n display key, step)
INSTITUTES: list[tuple[str, str, int]] = [
    ("INST_S2_A", "institute.s2_a", 2),  # Step 2 = ONE institute (UC-040)
    ("INST_S3_A", "institute.s3_a", 3),
    ("INST_S3_B", "institute.s3_b", 3),
    ("INST_S3_C", "institute.s3_c", 3),  # Step 3 = three fixed institutes
    ("INST_S4_A", "institute.s4_a", 4),
    ("INST_S4_B", "institute.s4_b", 4),  # Step 4 = two fixed institutes
]

# Valid codes for fast membership checks in validation.
INSTITUTE_CODES = frozenset(code for code, _key, _step in INSTITUTES)

# Which step each code belongs to, and the fixed set of codes required to complete each step (§3.6).
STEP_FOR_CODE = {code: step for code, _key, step in INSTITUTES}


# The Sorani names, for the **generated documents only**. The screens resolve `display_key`
# through i18next as before — this exists because a filed government document is written in
# Sorani whatever language the lawyer's interface is in, the same reason `summary.LABELS` holds
# Sorani status words. Printing the raw `INST_S3_A` on a signed cover sheet is what UC-058 hit.
INSTITUTE_NAMES_CKB: dict[str, str] = {
    "INST_S2_A": "سەرۆکایەتیی شارەوانیی سلێمانی",
    "INST_S3_A": "بەڕێوەبەرایەتیی تۆماری خانووبەرە ١",
    "INST_S3_B": "بەڕێوەبەرایەتیی تۆماری خانووبەرە ٢",
    "INST_S3_C": "بەڕێوەبەرایەتیی گشتیی شارەوانییەکان",
    "INST_S4_A": "لایەنی پەیوەندیدار",
    "INST_S4_B": "نەخشەی زەوی",
}


INSTITUTE_NAMES_EN: dict[str, str] = {
    "INST_S2_A": "Slemani Municipality Presidency",
    "INST_S3_A": "Real Estate Registration Directorate 1",
    "INST_S3_B": "Real Estate Registration Directorate 2",
    "INST_S3_C": "General Directorate of Municipalities",
    "INST_S4_A": "The relevant authority",
    "INST_S4_B": "Land map",
}


def name_ckb(code: str) -> str:
    """The Sorani name for a code, falling back to the code so a document never prints blank."""
    return INSTITUTE_NAMES_CKB.get(code, code or "")


def name_en(code: str) -> str:
    return INSTITUTE_NAMES_EN.get(code, code or "")


def codes_for_step(step: int) -> list[str]:
    return [code for code, _key, s in INSTITUTES if s == step]


def institutes_as_dicts() -> list[dict]:
    """Both names travel with every institute — the case screens print them together (UC-054).

    The pair is the same whatever language the interface is in, so it is served once from here
    rather than duplicated into all three translation files. `display_key` stays for anything that
    still wants a single localised name.
    """
    return [
        {
            "code": code,
            "display_key": key,
            "step": step,
            "name_ckb": name_ckb(code),
            "name_en": name_en(code),
        }
        for code, key, step in INSTITUTES
    ]
