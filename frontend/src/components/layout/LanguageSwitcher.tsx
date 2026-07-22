import { Languages } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useAppSelector } from "@/app/hooks";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useUpdatePreferencesMutation } from "@/features/auth/authApi";
import type { Language } from "@/features/auth/types";
import { SUPPORTED_LANGUAGES } from "@/i18n";

export function LanguageSwitcher() {
  const { t, i18n } = useTranslation();
  const isAuthed = useAppSelector((s) => Boolean(s.auth.access));
  const [updatePreferences] = useUpdatePreferencesMutation();

  const onSelect = (lang: Language) => {
    i18n.changeLanguage(lang); // also flips <html dir/lang> via the i18n listener
    if (isAuthed) updatePreferences({ language: lang });
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label={t("language.label")}>
          <Languages />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>{t("language.label")}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {SUPPORTED_LANGUAGES.map((lang) => (
          <DropdownMenuCheckItem
            key={lang}
            active={i18n.language === lang}
            onSelect={() => onSelect(lang)}
          >
            {t(`language.${lang}`)}
          </DropdownMenuCheckItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
