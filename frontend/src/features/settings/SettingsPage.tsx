import { Monitor, Moon, Palette, Sun, Type } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { useAppDispatch, useAppSelector } from "@/app/hooks";
import { FormSection } from "@/components/ui/separator";
import { PageHeader } from "@/features/common/PageHeader";
import { FontSpecimen } from "@/features/settings/FontSpecimen";
import { OptionCard } from "@/features/settings/OptionCard";
import { ThemePreview } from "@/features/settings/ThemePreview";
import {
  ACCENTS,
  FONTS,
  THEME_MODES,
  setAccent,
  setFont,
  setThemeMode,
  type ThemeMode,
} from "@/features/ui/uiSlice";

const MODE_ICONS: Record<ThemeMode, ReactNode> = {
  light: <Sun className="size-4" />,
  dark: <Moon className="size-4" />,
  system: <Monitor className="size-4" />,
};

// Each section is one single-select group; the radiogroup wrapper is what makes arrow keys walk
// the cards, and `FormSection` keeps the headings identical to the rest of the app.
function OptionGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div role="radiogroup" aria-label={label} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {children}
    </div>
  );
}

// Screen preferences, saved per machine in localStorage (§0 already records theme/language as
// deliberately client-only, so this follows the same deviation). Nothing here reaches the server.
export function SettingsPage() {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const { mode, theme, accent, font } = useAppSelector((s) => s.ui);

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <PageHeader title={t("settings.title")} description={t("settings.subtitle")} />

      <FormSection title={t("settings.appearance")} description={t("settings.appearanceHint")}>
        <OptionGroup label={t("settings.appearance")}>
          {THEME_MODES.map((option) => (
            <OptionCard
              key={option}
              name="theme-mode"
              value={option}
              selected={mode === option}
              onSelect={() => dispatch(setThemeMode(option))}
              title={t(`settings.modes.${option}`)}
              description={t(`settings.modeDesc.${option}`)}
              icon={MODE_ICONS[option]}
            >
              <ThemePreview mode={option} />
            </OptionCard>
          ))}
        </OptionGroup>
      </FormSection>

      <FormSection title={t("settings.accent")} description={t("settings.accentHint")}>
        <OptionGroup label={t("settings.accent")}>
          {ACCENTS.map((option) => (
            <OptionCard
              key={option}
              name="accent"
              value={option}
              selected={accent === option}
              onSelect={() => dispatch(setAccent(option))}
              title={t(`settings.accents.${option}`)}
              description={t(`settings.accentDesc.${option}`)}
              icon={<Palette className="size-4" />}
            >
              {/* The preview re-scopes the palette, so each card shows its own on a whole screen. */}
              <div data-accent={option}>
                <ThemePreview mode={theme} />
              </div>
            </OptionCard>
          ))}
        </OptionGroup>
      </FormSection>

      <FormSection title={t("settings.font")} description={t("settings.fontHint")}>
        <OptionGroup label={t("settings.font")}>
          {FONTS.map((option) => (
            <OptionCard
              key={option}
              name="font"
              value={option}
              selected={font === option}
              onSelect={() => dispatch(setFont(option))}
              title={t(`settings.fonts.${option}`)}
              description={t(`settings.fontDesc.${option}`)}
              icon={<Type className="size-4" />}
            >
              <FontSpecimen font={option} />
            </OptionCard>
          ))}
        </OptionGroup>
      </FormSection>

      <div className="space-y-1 text-xs text-muted-foreground">
        <p>{t("settings.fontVerified")}</p>
        <p>{t("settings.localOnly")}</p>
      </div>
    </div>
  );
}
