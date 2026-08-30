/** Digits, whatever script they were typed in (§9).
 *
 * The office writes numbers in Arabic-Indic (`٠١٢…`) and sometimes the Persian forms (`۰۱۲…`), so
 * every box that takes a number has to accept them — refusing them refuses a correctly typed
 * value. They are folded to ASCII on the way in, because what is stored has to be one string: a
 * PID is the "no land twice" dedup key (§5.7) and `١٩٩٠` and `1990` are different strings to an
 * index, and a date is parsed by the same rule.
 *
 * Lives here rather than in `pid.ts` because the national-ID box was the first to need it and is
 * no longer the only one — the date field folds the same way (UC-108).
 */

const FOLD: Record<string, string> = {};
"٠١٢٣٤٥٦٧٨٩".split("").forEach((d, i) => (FOLD[d] = String(i)));
"۰۱۲۳۴۵۶۷۸۹".split("").forEach((d, i) => (FOLD[d] = String(i)));

/** Every digit folded to ASCII, everything else left where it is — for text that still has to
 *  keep its shape, like the separators in a pasted date. */
export function foldDigits(value: string): string {
  let out = "";
  for (const ch of value) out += FOLD[ch] ?? ch;
  return out;
}

/** Everything in `value` that is a digit, folded to ASCII; everything else dropped. */
export function asciiDigits(value: string): string {
  let out = "";
  for (const ch of foldDigits(value)) {
    if (ch >= "0" && ch <= "9") out += ch;
  }
  return out;
}
