import { useEffect, useState } from "react";

/**
 * The value, settled for `delay` ms — so a filter fires one request per pause, not per keystroke.
 *
 * A `<input type="date">` emits a change per segment typed, and a text box one per character;
 * both would otherwise put a request on the wire for every intermediate state.
 */
export function useDebounced<T>(value: T, delay = 300): T {
  const [settled, setSettled] = useState(value);

  useEffect(() => {
    const id = setTimeout(() => setSettled(value), delay);
    return () => clearTimeout(id);
  }, [value, delay]);

  return settled;
}
