import { bidiIsolate } from "./format";

/** Keys DRF uses for whole-request errors — they name no field and must not be shown against one. */
const NON_FIELD_KEYS = new Set(["detail", "non_field_errors", "in_use"]);

/** A server message that is really an i18n key (`errors.phone.chars`), not a sentence.
 *
 * The domain validators answer with keys so the office reads them in Sorani (§9); DRF's own
 * built-in messages ("This field is required.") stay English sentences and are shown as sent.
 * The shape is unambiguous: dotted, no spaces, and always under the `errors.` namespace.
 */
const ERROR_KEY = /^errors(\.[A-Za-z][A-Za-z0-9]*)+$/;

/** A key that carries one runtime value: `errors.pid.taken:Karwan Ahmed`.
 *
 * The validators are otherwise **parameterless on purpose** — their bounds are constants and live
 * in the translation. A national ID's current holder is not a constant, and naming them is the
 * point: "already exists" leaves the lawyer to go and search for who. One value, always named
 * `name` in the translation, so the shape stays as narrow as the need. */
const ERROR_KEY_WITH_NAME = /^(errors(?:\.[A-Za-z][A-Za-z0-9]*)+):([\s\S]+)$/;

/** Render a server message: translate it when it is one of our keys, otherwise show it verbatim.
 *
 * The `!==` guard is the safety net — i18next returns the key itself when nothing matches, and a
 * raw `errors.phone.chars` in front of a user is worse than the English sentence it replaced.
 * `common.test_validation_keys` makes that unreachable; this keeps it harmless if it ever is.
 */
export function translateApiMessage(
  message: string,
  t?: (key: string, params?: Record<string, string>) => string,
): string {
  if (!t) return message;
  const named = ERROR_KEY_WITH_NAME.exec(message);
  if (named) {
    const [, key, name] = named;
    // Isolated, because this is the mixed-direction case §9 exists for: a Latin name dropped into
    // a Sorani sentence reorders the words around it without one, and a beneficiary's name is
    // exactly as likely to be Latin as Arabic-script in this office's data.
    const translated = t(key, { name: bidiIsolate(name) });
    return translated && translated !== key ? translated : message;
  }
  if (!ERROR_KEY.test(message)) return message;
  const translated = t(message);
  return translated && translated !== message ? translated : message;
}

/** Every field error in a DRF 400, flattened to `{ field: message }`.
 *
 * DRF **nests** errors under a nested serializer's own key: the intake endpoint posts the
 * beneficiary as `client_data`, so a bad birth date arrives as
 * `{"client_data": {"date_of_birth": ["Date has wrong format…"]}}`. The old reader took
 * `Object.values(data)[0]`, which is that inner **object** — neither a string nor an array of
 * them — so it fell through to the generic fallback and the user was told only "Could not save",
 * with nothing naming the field they had mistyped. Flattening is what makes those reachable.
 *
 * The leaf key wins (`client_data.date_of_birth` → `date_of_birth`) because that is what the form
 * calls its input. The API never collides on one: a beneficiary's birth date and their spouse's
 * are `date_of_birth` and `spouse_date_of_birth`, distinct all the way down.
 */
export function fieldErrors(
  err: unknown,
  t?: (key: string, params?: Record<string, string>) => string,
): Record<string, string> {
  const out: Record<string, string> = {};

  const walk = (node: unknown, key: string) => {
    if (typeof node === "string") {
      if (key && !out[key]) out[key] = translateApiMessage(node, t);
      return;
    }
    if (Array.isArray(node)) {
      // A list of messages for one field, or a per-item list for a list serializer.
      for (const item of node) walk(item, key);
      return;
    }
    if (node && typeof node === "object") {
      for (const [childKey, value] of Object.entries(node as Record<string, unknown>)) {
        if (NON_FIELD_KEYS.has(childKey)) continue;
        walk(value, childKey);
      }
    }
  };

  walk((err as { data?: unknown })?.data, "");
  return out;
}

/** Turn an RTK Query error into a human message: DRF's `detail`, else the first field error.
 *
 * `label` translates a field name for display, so the message says *which* input was wrong —
 * "Date of birth: Date has wrong format" rather than a bare "Date has wrong format" that leaves
 * the user hunting between their own and their spouse's.
 */
export function apiErrorMessage(
  err: unknown,
  fallback: string,
  label?: (field: string) => string | undefined,
  t?: (key: string, params?: Record<string, string>) => string,
): string {
  const data = (err as { data?: unknown })?.data;
  if (typeof data === "string" && data.trim()) return data;
  if (data && typeof data === "object") {
    const record = data as Record<string, unknown>;
    if (typeof record.detail === "string") return translateApiMessage(record.detail, t);
    const nonField = record.non_field_errors;
    if (Array.isArray(nonField) && typeof nonField[0] === "string")
      return translateApiMessage(nonField[0], t);

    const [field, message] = Object.entries(fieldErrors(err, t))[0] ?? [];
    if (message) {
      const name = label?.(field);
      return name ? `${name}: ${message}` : message;
    }
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
