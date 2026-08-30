/**
 * Names the office uses in **both** languages at once (UC-054, UC-088).
 *
 * Some things here are known by a Kurdish name on the paper and an English one in the ministry's
 * correspondence — the Step 2–4 institutes, and the municipality form. Picking a side loses half
 * the audience, so the screen prints the pair. Deliberately **not** localised: the pair is the
 * same in every interface language, which is why it is served with the record rather than
 * translated into all three files.
 *
 * Order is the caller's, because it is not the same everywhere: an institute leads with its
 * Kurdish name, the document slot with its English one. What must not differ is the joining, or
 * one screen ends up with an em dash and another with a slash.
 */
export function bilingualLabel(first: string, second: string): string {
  if (!first || !second || first === second) return first || second;
  return `${first} — ${second}`;
}
