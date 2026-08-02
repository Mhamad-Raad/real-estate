import { Check } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useAppDispatch, useAppSelector } from "@/app/hooks";
import { Card } from "@/components/ui/card";
import { FormSection } from "@/components/ui/separator";
import { PageHeader } from "@/features/common/PageHeader";
import {
  ACCENTS,
  FONTS,
  setAccent,
  setFont,
  type Accent,
  type FontChoice,
} from "@/features/ui/uiSlice";
import { cn } from "@/lib/utils";

// Screen preferences, saved per machine in localStorage (§0 already records theme/language as
// deliberately client-only, so this follows the same deviation). Nothing here reaches the server.
export function SettingsPage() {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const accent = useAppSelector((s) => s.ui.accent);
  const font = useAppSelector((s) => s.ui.font);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader title={t("settings.title")} description={t("settings.subtitle")} />

      <Card className="p-4">
        <FormSection title={t("settings.accent")} description={t("settings.accentHint")}>
          <div className="flex flex-wrap gap-2">
            {ACCENTS.map((name) => (
              <button
                key={name}
                type="button"
                onClick={() => dispatch(setAccent(name as Accent))}
                aria-pressed={accent === name}
                aria-label={t(`settings.accents.${name}`)}
                title={t(`settings.accents.${name}`)}
                // Each swatch previews itself by scoping the preset to its own subtree.
                data-accent={name}
                className={cn(
                  "flex size-10 items-center justify-center rounded-full border-2 transition-transform hover:scale-105",
                  accent === name ? "border-foreground" : "border-transparent",
                )}
              >
                <span className="accent-swatch flex size-7 items-center justify-center rounded-full">
                  {accent === name && <Check className="size-4" strokeWidth={3} />}
                </span>
              </button>
            ))}
          </div>
        </FormSection>
      </Card>

      <Card className="p-4">
        <FormSection title={t("settings.font")} description={t("settings.fontHint")}>
          <div className="grid gap-2 sm:grid-cols-2">
            {FONTS.map((name) => (
              <button
                key={name}
                type="button"
                onClick={() => dispatch(setFont(name as FontChoice))}
                aria-pressed={font === name}
                data-font={name}
                className={cn(
                  "flex flex-col items-start gap-1 rounded-md border p-3 text-start transition-colors",
                  font === name ? "border-primary bg-primary/5" : "border-border hover:bg-accent/50",
                )}
              >
                <span className="text-sm font-medium">{t(`settings.fonts.${name}`)}</span>
                {/* The specimen carries the Sorani letters that rule most Arabic faces out. */}
                <span className="text-lg" style={{ fontFamily: "var(--font-arabic)" }} lang="ckb">
                  ئەم نووسینە ڕەنگە پۆلێ گەورە بێت
                </span>
              </button>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">{t("settings.fontVerified")}</p>
        </FormSection>
      </Card>

      <p className="text-xs text-muted-foreground">{t("settings.localOnly")}</p>
    </div>
  );
}
