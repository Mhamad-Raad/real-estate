/** What a phone box will accept as it is typed (§4.1).
 *
 * The server already refuses a bad number, but a field that silently swallows `sajnasfnasfns`
 * until you press Save is a worse experience than one that never took it: the lawyer finds out at
 * the end of the form instead of at the keystroke. So this is a *convenience*, not the boundary —
 * `common/validators.validate_phone` remains the rule, and these limits deliberately mirror it.
 *
 * **Arabic-Indic digits are digits** (`٠١٢…`, and the Persian `۰۱۲…`). The office writes numbers in
 * that script, and stripping them here would be the same defect the backend had.
 */

/** Longest national number the office uses — `07XXXXXXXXX`. Mirrors `PHONE_MAX_DIGITS`. */
export const PHONE_MAX_DIGITS = 11;
/** With a country code written out: `+964` + the national number, minus its leading zero. */
export const PHONE_MAX_DIGITS_WITH_COUNTRY_CODE = PHONE_MAX_DIGITS + 3;

const DIGIT = /[0-9٠-٩۰-۹]/;
// The separators people actually type. **No dash** (user decision, 2026-08-11): the office writes
// its numbers as digits, optionally spaced, and a `-` only ever arrived as a slip. Anything else —
// a letter above all — is not part of a number and is dropped as it is typed.
const SEPARATOR = /[\s()]/;

/** The typed value, reduced to what a phone number may contain and capped at its longest form.
 *
 * Applied on every keystroke, so it must be forgiving of a half-typed value: it never reorders or
 * reformats what the user has, it only refuses to add what cannot belong.
 */
export function sanitisePhoneInput(raw: string): string {
  // A `+` is only meaningful as the very first character; typed mid-number it is a slip.
  const leadingPlus = raw.trimStart().startsWith("+");
  const maxDigits = leadingPlus ? PHONE_MAX_DIGITS_WITH_COUNTRY_CODE : PHONE_MAX_DIGITS;

  let digits = 0;
  let out = leadingPlus ? "+" : "";
  for (const char of raw) {
    if (DIGIT.test(char)) {
      if (digits >= maxDigits) continue; // full — extra digits are dropped, not the earlier ones
      digits += 1;
      out += char;
    } else if (SEPARATOR.test(char)) {
      out += char;
    }
    // Everything else (letters, punctuation, a second `+`) is silently refused.
  }
  return out;
}
