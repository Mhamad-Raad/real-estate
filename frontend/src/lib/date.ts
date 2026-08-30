/** The calendar arithmetic behind the date field (UC-108).
 *
 * Pure and free of React so the rules can be tested as rules. Dates travel as ISO `YYYY-MM-DD`
 * everywhere — that is what the API stores and what every caller already passes — while the
 * office reads and types **day / month / year**; this module is the only place the two meet.
 */

import { asciiDigits, foldDigits } from "./digits";

/** The bounds a typed year must land in to be a date somebody meant rather than one still being
 *  typed — the window that replaced `useAutosave`'s old half-typed guard (UC-072, UC-108). */
export const MIN_YEAR = 1900;
export const MAX_YEAR = 2200;

export interface DateParts {
  day: string;
  month: string;
  year: string;
}

export const EMPTY_PARTS: DateParts = { day: "", month: "", year: "" };

/** How many days a month really has, leap years included. */
export function daysInMonth(year: number, month: number): number {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

/** Whether these three numbers name a real day. `31/02` is not one, and neither is a year outside
 *  the window above — both are refused rather than silently rolled forward, which is what
 *  `new Date()` would do (31 February becomes 3 March). */
export function isRealDate(year: number, month: number, day: number): boolean {
  if (!Number.isInteger(year) || year < MIN_YEAR || year > MAX_YEAR) return false;
  if (!Number.isInteger(month) || month < 1 || month > 12) return false;
  return Number.isInteger(day) && day >= 1 && day <= daysInMonth(year, month);
}

/** Split an ISO date into the three boxes. Anything unparseable comes back empty rather than
 *  half-filled — a field showing two thirds of a value nobody stored is worse than an empty one. */
export function toParts(iso: string | null | undefined): DateParts {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso ?? "");
  if (!match) return EMPTY_PARTS;
  const [, year, month, day] = match;
  return { day, month, year };
}

/** The three boxes as an ISO date, or `null` while they do not yet name one.
 *
 * `null` is the whole point: it is what stops a half-typed year reaching the server. Typing 2026
 * passes through 2, 20 and 202, and each of those **is** a valid `<input type="date">` value —
 * which is exactly how the year 2 came to be saved (UC-072). Here it simply is not a date yet. */
export function toIso(parts: DateParts): string | null {
  if (!parts.day || !parts.month || !parts.year) return null;
  const year = Number(parts.year);
  const month = Number(parts.month);
  const day = Number(parts.day);
  if (parts.year.length !== 4 || !isRealDate(year, month, day)) return null;
  return `${String(year).padStart(4, "0")}-${pad(month)}-${pad(day)}`;
}

export function pad(value: number): string {
  return String(value).padStart(2, "0");
}

/** Whether every box is empty — a cleared field, which is a real edit and not a half-typed one. */
export function isBlank(parts: DateParts): boolean {
  return !parts.day && !parts.month && !parts.year;
}

/** What a segment keeps of what was typed into it: digits in any script, folded, capped. */
export function segmentInput(value: string, max: number): string {
  return asciiDigits(value).slice(0, max);
}

/** A segment is finished — move the cursor on — when it is full, or when what was typed can no
 *  longer grow into anything valid (a `5` in the month box is May and cannot become anything
 *  else). Without this the office would tab three times per date. */
export function segmentIsFinished(kind: "day" | "month" | "year", text: string): boolean {
  if (kind === "year") return text.length === 4;
  if (text.length === 2) return true;
  const first = Number(text);
  return text.length === 1 && first > (kind === "month" ? 1 : 3);
}

/** How a box reads once the cursor has left it: a lone day or month digit gains its zero, so the
 *  office sees `05` and `09` rather than `5` and `9` — the shape a date is written in.
 *
 *  Only on the way **out**. Padding a `1` in the month box the moment it is typed would make `12`
 *  unreachable. A lone `0` is left alone: it is not a day, and the field's own revert deals with
 *  it like any other half-typed value.
 */
export function settledSegment(kind: keyof DateParts, text: string): string {
  return kind !== "year" && text.length === 1 && Number(text) > 0 ? pad(Number(text)) : text;
}

/** One box a step up or down, the way the arrow keys move a native date input.
 *
 * Day and month **wrap** — 12 up is January, not a dead end — while the year clamps at the window
 * a typed date may land in. An empty box starts somewhere useful rather than at zero: the year on
 * this year, the others at whichever end the arrow came from.
 */
export function stepSegment(kind: keyof DateParts, parts: DateParts, by: number): string {
  if (kind === "year") {
    const from = Number(parts.year) || new Date().getFullYear();
    const year = parts.year ? clamp(from + by, MIN_YEAR, MAX_YEAR) : from;
    return String(year).padStart(4, "0");
  }
  const max =
    kind === "month"
      ? 12
      : // The month's real length once it is known — 31 is the honest guess until then.
        isRealDate(Number(parts.year), Number(parts.month), 1)
        ? daysInMonth(Number(parts.year), Number(parts.month))
        : 31;
  const from = Number(parts[kind]) || (by > 0 ? 0 : max + 1);
  return pad(wrap(from + by, 1, max));
}

function clamp(value: number, low: number, high: number): number {
  return Math.min(Math.max(value, low), high);
}

function wrap(value: number, low: number, high: number): number {
  const span = high - low + 1;
  return ((((value - low) % span) + span) % span) + low;
}

/** A whole date pasted into one of the boxes (a native date input took one; this keeps parity).
 *
 * Two shapes, and the order is never guessed: **ISO** `2026-08-05`, which is what a copy out of
 * this app or a report gives, and **day-first** `5/8/2026`, which is what the office reads off
 * the paperwork. A bare run of digits is refused — `05082026` and `20260805` look alike and
 * guessing wrong writes a date nobody typed.
 */
export function parsePasted(text: string): DateParts | null {
  // Folded first, because the office pastes ٢٠٢٦-٠٨-٠٥ as readily as 2026-08-05. A bare run of
  // digits matches neither pattern and is therefore refused, which is the intent.
  const clean = foldDigits(text.trim());
  const iso = /^(\d{4})\D(\d{1,2})\D(\d{1,2})$/.exec(clean);
  if (iso) return partsIfReal(iso[1], iso[2], iso[3]);
  const dayFirst = /^(\d{1,2})\D(\d{1,2})\D(\d{4})$/.exec(clean);
  if (dayFirst) return partsIfReal(dayFirst[3], dayFirst[2], dayFirst[1]);
  return null;
}

function partsIfReal(year: string, month: string, day: string): DateParts | null {
  const parts = { year, month: pad(Number(month)), day: pad(Number(day)) };
  return toIso(parts) ? parts : null;
}

/** The weeks of one month as a grid, blank-padded so every row holds seven cells.
 *  `weekStart` is a JS day number (0 = Sunday). */
export function monthGrid(year: number, month: number, weekStart: number): (number | null)[][] {
  const lead = (new Date(Date.UTC(year, month - 1, 1)).getUTCDay() - weekStart + 7) % 7;
  const days = daysInMonth(year, month);
  const cells: (number | null)[] = [...Array(lead).fill(null), ...range(1, days)];
  while (cells.length % 7) cells.push(null);
  return Array.from({ length: cells.length / 7 }, (_, week) => cells.slice(week * 7, week * 7 + 7));
}

/** Shift a year/month pair by whole months, carrying the year. */
export function shiftMonth(year: number, month: number, by: number): { year: number; month: number } {
  const zero = year * 12 + (month - 1) + by;
  return { year: Math.floor(zero / 12), month: (zero % 12) + 1 };
}

function range(from: number, to: number): number[] {
  return Array.from({ length: to - from + 1 }, (_, i) => from + i);
}
