/**
 * Drop blank filter values so they never reach the server as `?category=`.
 *
 * Shared by every filtered list: an empty string is "no filter", but the server reads it as a
 * filter matching nothing.
 */
export function cleanParams<T extends object>(filters: T): Record<string, string> {
  return Object.fromEntries(
    Object.entries(filters)
      .filter(([, value]) => value !== "" && value !== undefined && value !== null)
      .map(([key, value]) => [key, String(value)]),
  );
}
