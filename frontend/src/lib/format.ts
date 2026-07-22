// Locale-aware, bidi-safe formatting for numbers and dates (§9).
// Wrapping output in a First-Strong Isolate keeps numerals/dates from breaking the
// surrounding RTL text order when mixed into a sentence.

const FSI = "⁨"; // First Strong Isolate
const PDI = "⁩"; // Pop Directional Isolate

// Kurdish Sorani has no dedicated Intl data; fall back to Arabic's for correct digits/calendar.
function intlLocale(lang: string): string {
  return lang === "ckb" ? "ar" : lang;
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
