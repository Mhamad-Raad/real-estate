import { useCallback, useEffect, useRef, useState } from "react";

/**
 * A group of fields that save themselves, without the server overwriting what is being typed.
 *
 * Two problems solved together (UC-072). A field that PATCHed on every change put one request on
 * the wire per keystroke; worse, the refetch that followed wrote the *server's* value back into a
 * control the user was still editing.
 *
 * So while a field is dirty the draft wins, one request goes out per pause carrying **every**
 * pending field, and the draft is dropped only once the server echoes the same value back.
 *
 * It used to carry a second guard — a `persist: false` that showed an edit without queueing it —
 * because a native date input reported the year 2026 as four *valid* dates on its way through
 * 0002, 0020 and 0202. `DateField` settled that at the source (UC-108): a date reaches here only
 * once it names a real day, so nothing half-typed ever arrives and the guard is gone.
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

  /** Records an edit and queues it for the next pause. */
  const set = useCallback(
    <K extends keyof T>(key: K, value: T[K]) => {
      setDraft((current) => ({ ...current, [key]: value }));
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
