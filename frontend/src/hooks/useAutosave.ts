import { useCallback, useEffect, useRef, useState } from "react";

/**
 * A group of fields that save themselves, without the server overwriting what is being typed.
 *
 * Two problems solved together (UC-072). A field that PATCHed on every change put one request on
 * the wire per keystroke; worse, the refetch that followed wrote the *server's* value back into a
 * control the user was still editing. On a `<input type="date">` that is not cosmetic: typing the
 * year 2026 produces four **valid** dates — 0002, 0020, 0202, 2026 — so the field visibly reset to
 * year 2 while the lawyer was typing it.
 *
 * So while a field is dirty the draft wins, one request goes out per pause carrying **every**
 * pending field, and the draft is dropped only once the server echoes the same value back.
 */
export function useAutosave<T extends Record<string, unknown>>({
  saved,
  onSave,
  delay = 700,
}: {
  /** The values as the server currently has them. */
  saved: T;
  /** Persists one merged patch. Rebuilt each render so it closes over the current row version. */
  onSave: (patch: Partial<T>) => unknown;
  delay?: number;
}) {
  const [draft, setDraft] = useState<Partial<T>>({});
  const pending = useRef<Partial<T>>({});
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  // The timer must call the newest saver: `onSave` closes over the row's `version`, and firing an
  // older one would PATCH against a stale version and come back 409 (§12 optimistic locking).
  const saveRef = useRef(onSave);
  saveRef.current = onSave;

  // Retiring a draft key when the server agrees — rather than when the response lands — is what
  // stops the control flickering back to the old value in the gap before the refetch arrives.
  useEffect(() => {
    setDraft((current) => {
      const next = { ...current };
      let changed = false;
      for (const key of Object.keys(next) as (keyof T)[]) {
        if (Object.is(saved[key], next[key])) {
          delete next[key];
          changed = true;
        }
      }
      return changed ? next : current;
    });
  }, [saved]);

  const flush = useCallback(() => {
    clearTimeout(timer.current);
    const patch = pending.current;
    pending.current = {};
    if (Object.keys(patch).length > 0) saveRef.current(patch);
  }, []);

  /** Records an edit; `persist: false` shows it but holds it back (a half-typed date). */
  const set = useCallback(
    <K extends keyof T>(key: K, value: T[K], persist = true) => {
      setDraft((current) => ({ ...current, [key]: value }));
      if (!persist) return;
      pending.current = { ...pending.current, [key]: value };
      clearTimeout(timer.current);
      timer.current = setTimeout(flush, delay);
    },
    [delay, flush],
  );

  /** Records an edit and sends it at once — for a control with no intermediate states, like a
   *  dropdown. Routed through the same queue so it cannot overtake a pending edit's version. */
  const commit = useCallback(
    <K extends keyof T>(key: K, value: T[K]) => {
      set(key, value);
      flush();
    },
    [set, flush],
  );

  // Collapsing a step unmounts its panel (the accordion only mounts the open one), so without this
  // the last thing typed before closing it would be dropped on the floor.
  useEffect(() => () => flush(), [flush]);

  const value = <K extends keyof T>(key: K): T[K] =>
    key in draft ? (draft[key] as T[K]) : saved[key];

  return { value, set, commit, flush };
}

/**
 * Whether a date is worth sending yet. A date input reports a valid value the moment its year has
 * one digit, so a year under 1900 means "still being typed", not a date anyone means (§5.2).
 */
export function isSettledDate(value: string): boolean {
  if (!value) return true; // clearing the field is a real edit
  const year = Number(value.slice(0, 4));
  return year >= 1900 && year <= 2200;
}
