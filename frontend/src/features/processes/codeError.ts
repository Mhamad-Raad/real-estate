import type { TFunction } from "i18next";

import { apiErrorKey, apiErrorMessage } from "@/lib/apiError";

/**
 * Turn a refused case number into a sentence the office can read (UC-062).
 *
 * The server sends `code_error` beside its English `unique_code` message; anything it does not
 * recognise falls back to that message, so a new server-side reason still says *something* useful
 * rather than a generic failure. Shared by intake and the case page so the two cannot drift.
 */
export function codeErrorMessage(err: unknown, t: TFunction, fallback: string): string {
  const reason = apiErrorKey(err, "code_error");
  if (!reason) return apiErrorMessage(err, fallback);
  return t(`workflow.codeError.${reason}`, {
    defaultValue: apiErrorMessage(err, fallback),
    prefix: apiErrorKey(err, "expected_prefix") ?? "",
  });
}
