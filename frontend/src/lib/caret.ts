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
 * **The new position is counted, not subtracted.** Running the filter over the text *before* the
 * caret says how many of those characters survived, which is exactly where the caret belongs. The
 * obvious `caret - (removed characters)` is wrong for any filter that also drops from the **end**:
 * measured on the ID box's 12-digit cap, typing into the middle of a full number left the caret
 * one place short — *before* the digit just typed — so the next two digits came out transposed.
 */
export function filterKeepingCaret(el: HTMLInputElement, filter: (raw: string) => string): string {
  const next = filter(el.value);
  // Nothing was refused, so React renders what the box already holds and the browser's own caret
  // stands. Touching the selection here would be pure interference on every ordinary keystroke.
  if (next === el.value) return next;

  const caret = el.selectionStart;
  // A box whose type carries no selection (`date`, `number`) reports null and would throw below.
  if (caret === null) return next;

  const at = Math.min(filter(el.value.slice(0, caret)).length, next.length);
  // After the event, so it runs once React has restored the value it rendered.
  queueMicrotask(() => {
    if (el.isConnected) el.setSelectionRange(at, at);
  });
  return next;
}
