import { useTranslation } from "react-i18next";
import { Toaster as Sonner } from "sonner";

import { useAppSelector } from "@/app/hooks";
import { dirFor } from "@/i18n";

// App-wide toast host, wired to the current theme and text direction (RTL-aware).
export function Toaster() {
  const theme = useAppSelector((s) => s.ui.theme);
  const { i18n } = useTranslation();
  return (
    <Sonner
      theme={theme}
      dir={dirFor(i18n.language)}
      position={dirFor(i18n.language) === "rtl" ? "top-left" : "top-right"}
      richColors
      closeButton
    />
  );
}
