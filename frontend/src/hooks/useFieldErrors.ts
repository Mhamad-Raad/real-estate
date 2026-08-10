import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";

import { fieldErrors } from "@/lib/apiError";

/** Per-field server errors for one form, and the plumbing to clear them as the user fixes things.
 *
 * The server is the boundary (§7.2) — client-side checks only make the feedback immediate, they
 * never decide what is allowed. So the authoritative message for a field is whatever the API
 * said about it, and this holds exactly that.
 *
 * `prefix` is for a form that renders the same field twice: the intake page shows a birth date
 * for the beneficiary and another for their spouse, and DRF names both `date_of_birth`.
 */
export function useFieldErrors(prefix = "") {
  const { t } = useTranslation();
  const [errors, setErrors] = useState<Record<string, string>>({});

  /** Take a caught RTK Query error and mark every field it named. */
  const setFromError = useCallback(
    (err: unknown) => {
      const found = fieldErrors(err, prefix, t);
      setErrors(found);
      return found;
    },
    [prefix, t],
  );

  /** Drop one field's error — call it as the user edits, so a corrected input stops looking wrong
   * immediately rather than staying red until the next round trip. */
  const clear = useCallback((field: string) => {
    setErrors((current) => {
      if (!current[field]) return current; // same object: no re-render for an unaffected keystroke
      const { [field]: _dropped, ...rest } = current;
      return rest;
    });
  }, []);

  const clearAll = useCallback(() => setErrors({}), []);

  return { errors, setFromError, setErrors, clear, clearAll };
}
