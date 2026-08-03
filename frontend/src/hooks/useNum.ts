import { useTranslation } from "react-i18next";

import { formatNumber } from "@/lib/format";

/**
 * The current language's digits. Anything interpolated into a translated string must go through
 * this: i18next substitutes `{{x}}` verbatim, so a raw number prints Latin `1234` beside Sorani
 * text that everywhere else reads ١٢٣٤ (§9). Three screens each declared this same one-liner.
 */
export function useNum() {
  const { i18n } = useTranslation();
  return (value: number) => formatNumber(value, i18n.language);
}
