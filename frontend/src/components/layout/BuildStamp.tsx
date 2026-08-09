import { useTranslation } from "react-i18next";

import { buildStamp } from "@/lib/build";
import { cn } from "@/lib/utils";

/**
 * The version, shown to the office so they can read it back during a support call.
 *
 * The digits are deliberately Latin and NOT routed through `useNum`: this is the one exception
 * to §9's Sorani-digit rule, because the string has to match what is in git and what someone
 * types into a bug report. Converting it to ١.٠.٠ would destroy its only purpose — do not "fix"
 * it in a digit sweep.
 */
export function BuildStamp({ className }: { className?: string }) {
  const { t } = useTranslation();
  return (
    <p
      aria-label={`${t("app.version")}: ${buildStamp}`}
      className={cn("font-mono text-[11px] text-muted-foreground", className)}
    >
      {/* The paragraph follows the page direction so it aligns with whatever it sits under;
          only the string is isolated, because it mixes Latin digits with parens and an RTL
          page would otherwise swing the "(build 1)" to the wrong end. */}
      <span dir="ltr">{buildStamp}</span>
    </p>
  );
}
