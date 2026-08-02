/**
 * The default reporting window, mirroring the backend's `reports.selectors.WINDOW_DAYS`.
 *
 * Same precedent as `PAGE_SIZE` in `services/types.ts`: a constant the server owns, restated once
 * on the client so the dashboard and the Reports page cannot drift apart (§10.1, UC-001/UC-017).
 */
export const WINDOW_DAYS = 30;

/**
 * `YYYY-MM-DD` in the **local** timezone.
 *
 * Not `toISOString()`, which converts to UTC first — east of Greenwich that reports "yesterday"
 * for anything after midnight local, so the office would see a window off by a day.
 */
export function toLocalISODate(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** The inclusive `date_from`/`date_to` pair covering the last `days` days, today included. */
export function lastNDays(days: number = WINDOW_DAYS): { date_from: string; date_to: string } {
  const to = new Date();
  const from = new Date();
  from.setDate(from.getDate() - days);
  return { date_from: toLocalISODate(from), date_to: toLocalISODate(to) };
}
