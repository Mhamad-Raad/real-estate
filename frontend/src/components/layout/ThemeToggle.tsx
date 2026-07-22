import { Moon, Sun } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useAppDispatch, useAppSelector } from "@/app/hooks";
import { Button } from "@/components/ui/button";
import { toggleTheme } from "@/features/ui/uiSlice";
import { useUpdatePreferencesMutation } from "@/features/auth/authApi";

export function ThemeToggle() {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const theme = useAppSelector((s) => s.ui.theme);
  const isAuthed = useAppSelector((s) => Boolean(s.auth.access));
  const [updatePreferences] = useUpdatePreferencesMutation();

  const onToggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    dispatch(toggleTheme());
    // Persist the choice to the user's profile so it follows them across devices.
    if (isAuthed) updatePreferences({ theme: next });
  };

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
