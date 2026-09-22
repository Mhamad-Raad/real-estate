/** Filtering a box as it is typed, without throwing the typist out of the middle of the word.
 *
 * A controlled input whose `onChange` refuses a character ends up with a DOM value React did not
 * render, so React puts its own value back — and that assignment **drops the caret at the end of
 * the field**. Measured, not assumed: typing a digit into the middle of "Karwan Ahmed" left the
 * text correctly unchanged and moved the caret from 6 to 12, so the next letter landed at the end
 * of the name. The longer the field, the worse it reads, and a name is the longest one here.
 */

/**
 * `filter` applied to what the box now holds, with the caret put back where the typist left it.
 *
 * Assumes the filter drops characters **at or before** the caret — true of a keystroke filter,
 * which only ever refuses what was just typed. A filter that also trims the end (the ID box's
 * 12-digit cap) would need the correction computed from the two strings instead.
 */
export function filterKeepingCaret(el: HTMLInputElement, filter: (raw: string) => string): string {
  const next = filter(el.value);
  const caret = el.selectionStart;
  // A box whose type carries no selection (`date`, `number`) reports null and would throw below.
  if (caret === null) return next;

  const at = Math.min(Math.max(0, caret - (el.value.length - next.length)), next.length);
  // After the event, so it runs once React has restored the value it rendered.
  queueMicrotask(() => {
    if (el.isConnected) el.setSelectionRange(at, at);
  });
  return next;
}
