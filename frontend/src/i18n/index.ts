import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import ar from "./locales/ar.json";
import ckb from "./locales/ckb.json";
import en from "./locales/en.json";

export const SUPPORTED_LANGUAGES = ["ckb", "ar", "en"] as const;
export type Language = (typeof SUPPORTED_LANGUAGES)[number];

// Arabic-script languages render right-to-left.
export const RTL_LANGUAGES: Language[] = ["ckb", "ar"];

export function dirFor(lang: string): "rtl" | "ltr" {
  return RTL_LANGUAGES.includes(lang as Language) ? "rtl" : "ltr";
}

// Reflect the active language onto <html> so CSS (:lang, [dir]) and the browser agree.
export function applyHtmlLangDir(lang: string) {
  const el = document.documentElement;
  el.setAttribute("lang", lang);
  el.setAttribute("dir", dirFor(lang));
}

const stored = localStorage.getItem("language");
const initialLang: Language = SUPPORTED_LANGUAGES.includes(stored as Language)
  ? (stored as Language)
  : "ckb";

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    ar: { translation: ar },
    ckb: { translation: ckb },
  },
  lng: initialLang,
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

applyHtmlLangDir(initialLang);
i18n.on("languageChanged", (lng) => {
  localStorage.setItem("language", lng);
  applyHtmlLangDir(lng);
});

export default i18n;
