// Turn an RTK Query error into a human message: prefer DRF's `detail` or the first field error.
export function apiErrorMessage(err: unknown, fallback: string): string {
  const data = (err as { data?: unknown })?.data;
  if (typeof data === "string" && data.trim()) return data;
  if (data && typeof data === "object") {
    const record = data as Record<string, unknown>;
    if (typeof record.detail === "string") return record.detail;
    const first = Object.values(record)[0];
    if (Array.isArray(first) && typeof first[0] === "string") return first[0];
    if (typeof first === "string") return first;
  }
  return fallback;
}

// HTTP status of an RTK Query error, when present (e.g. 409 duplicate, 401 auth).
export function apiErrorStatus(err: unknown): number | undefined {
  return (err as { status?: number })?.status;
}

/** How many live records blocked a delete, when the server refused one for being in use.
 *
 * The backend answers with `{in_use: {<relation>: <count>}}` rather than a sentence, so the
 * message the user reads is composed and translated here — the server's `detail` is English and
 * every screen in this app is localized (§9).
 */
export function apiInUseTotal(err: unknown): number | undefined {
  const inUse = (err as { data?: { in_use?: unknown } })?.data?.in_use;
  if (!inUse || typeof inUse !== "object") return undefined;
  // DRF renders error details as strings, so the counts arrive as "9", not 9.
  const counts = Object.values(inUse as Record<string, unknown>)
    .map(Number)
    .filter((n) => Number.isFinite(n) && n > 0);
  return counts.length ? counts.reduce((a, b) => a + b, 0) : undefined;
}
