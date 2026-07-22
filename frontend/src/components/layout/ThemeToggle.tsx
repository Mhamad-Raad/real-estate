import { Moon, Sun } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useAppDispatch, useAppSelector } from "@/app/hooks";
import { Button } from "@/components/ui/button";
import { toggleTheme } from "@/features/ui/uiSlice";

export function ThemeToggle() {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const theme = useAppSelector((s) => s.ui.theme);

  // Theme lives only in the browser (uiSlice persists it to localStorage).
  const onToggle = () => dispatch(toggleTheme());

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={onToggle}
      aria-label={theme === "dark" ? t("theme.toLight") : t("theme.toDark")}
      title={theme === "dark" ? t("theme.toLight") : t("theme.toDark")}
    >
      {theme === "dark" ? <Sun /> : <Moon />}
    </Button>
  );
}
