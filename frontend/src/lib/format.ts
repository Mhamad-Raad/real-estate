// Locale-aware, bidi-safe formatting for numbers and dates (§9).
// Wrapping output in a First-Strong Isolate keeps numerals/dates from breaking the
// surrounding RTL text order when mixed into a sentence.

const FSI = "⁨"; // First Strong Isolate
const PDI = "⁩"; // Pop Directional Isolate

// Kurdish Sorani has no dedicated Intl date data, so both RTL languages use Arabic's month names.
// The numbering system is pinned explicitly: modern CLDR resolves plain `ar` to LATIN digits, so
// the fallback alone would print 1234 on screen while the generated letters print ١٢٣٤ (§6.6).
function intlLocale(lang: string): string {
  return lang === "en" ? "en" : "ar-u-nu-arab";
}

export function bidiIsolate(text: string): string {
  return `${FSI}${text}${PDI}`;
}

export function formatNumber(
  value: number,
  lang: string,
  options?: Intl.NumberFormatOptions,
): string {
  return bidiIsolate(new Intl.NumberFormat(intlLocale(lang), options).format(value));
}

export function formatDate(
  value: Date | string | number,
  lang: string,
  options: Intl.DateTimeFormatOptions = { year: "numeric", month: "short", day: "numeric" },
): string {
  const date = value instanceof Date ? value : new Date(value);
  return bidiIsolate(new Intl.DateTimeFormat(intlLocale(lang), options).format(date));
}
