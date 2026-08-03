"""The ONE definition of the Step 2–4 institutes (§3.4).

Backend validates `ProcessInstituteEntry.institute_code` against this; the frontend fetches it
read-only via GET /api/v1/institutes/ and never hard-codes it. Display names are i18n keys, so
the machine `code` is stable in the DB while ckb/ar/en labels come from the translation files.
Names are placeholders per the spec.
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


def codes_for_step(step: int) -> list[str]:
    return [code for code, _key, s in INSTITUTES if s == step]


def institutes_as_dicts() -> list[dict]:
    return [{"code": code, "display_key": key, "step": step} for code, key, step in INSTITUTES]
