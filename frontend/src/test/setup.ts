import "@testing-library/jest-dom/vitest";

import i18n from "@/i18n";

// Tests assert against English strings; force it before any component renders.
await i18n.changeLanguage("en");
