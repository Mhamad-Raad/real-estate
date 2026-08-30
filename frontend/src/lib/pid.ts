/** What a national-ID box will accept as it is typed (§4.1, office rule 2026-08-20).
 *
 * The server is the boundary — `common/validators.validate_pid` — and this only spares the lawyer
 * from discovering at Save that a field swallowed a letter. Same relationship as
 * `phone.ts`, and it must be kept in step with the validator for the same reason: if the two
 * drift, the box and the API disagree about one field.
 *
 * **Arabic-Indic digits are digits** (`٠١٢…`, Persian `۰۱۲…`). The office writes numbers in that
 * script, so refusing them here would refuse a correctly-typed ID. They are folded to ASCII on the
 * way in, because the PID is the "no land twice" dedup key (§5.7) and `١٩٩٠` and `1990` are
 * different strings to an index — accepting both unfolded would open a duplicate through the guard.
 * The folding itself is shared with every other numeric box (`lib/digits.ts`).
 */

import { asciiDigits } from "./digits";

/** Mirrors `validators.PID_MAX_DIGITS` — a ceiling, not a length (the office, 2026-08-30). */
export const PID_MAX_DIGITS = 12;

/**
 * Digits only, folded to ASCII, capped at `PID_MAX_DIGITS`.
 *
 * **Overflow drops from the END**, as the phone box does: truncating the start would rewrite a
 * number under the lawyer's cursor mid-type.
 */
export function filterPid(value: string): string {
  return asciiDigits(value).slice(0, PID_MAX_DIGITS);
}
