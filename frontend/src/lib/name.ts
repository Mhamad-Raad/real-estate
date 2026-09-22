/** What a name box will accept as it is typed (§4.1, the office's rule 2026-09-22).
 *
 * A person's name never carries a number, and one that slips in is not caught anywhere later —
 * it is copied onto the generated letter and printed. So the box refuses a digit at the keystroke,
 * the same convenience `phone.ts` and `pid.ts` give their fields.
 *
 * **Arabic-Indic digits are digits** (`٠١٢…`, Persian `۰۱۲…`): the office types numbers in that
 * script, so an ASCII-only rule would let `١٩٩٠` into the field it had just refused `1990` from.
 *
 * Only digits are dropped. A name may legitimately carry a hyphen, an apostrophe, a full stop or
 * an Arabic diacritic, and refusing those would refuse real names.
 */

import { withoutDigits } from "./digits";

/**
 * The typed value with every digit removed, in whatever script it was written.
 *
 * Applied on each keystroke, so it never trims, reorders or reformats what is already in the box —
 * it only refuses to add what cannot belong in a name.
 */
export function filterName(value: string): string {
  return withoutDigits(value);
}
