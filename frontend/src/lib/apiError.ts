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
