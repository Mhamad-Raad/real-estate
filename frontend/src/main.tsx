import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Provider } from "react-redux";
import { BrowserRouter } from "react-router-dom";

// Bundled offline fonts (no CDN) — Vazirmatn for Arabic/Kurdish, Inter for Latin.
import "@fontsource-variable/vazirmatn";
import "@fontsource-variable/inter";
// Selectable faces (UC-015/UC-033). Each was verified to cover the Sorani letters before being
// offered; all are bundled, because the app runs with no internet at all (§12). The static
// families are pulled in at the two weights the UI actually uses — importing the package root
// would ship seven weights of each and bloat `dist` for nothing.
import "@fontsource-variable/noto-sans-arabic";
import "@fontsource-variable/noto-naskh-arabic";
import "@fontsource-variable/noto-kufi-arabic";
import "@fontsource-variable/reem-kufi";
import "@fontsource/ibm-plex-sans-arabic/400.css";
import "@fontsource/ibm-plex-sans-arabic/600.css";
import "@fontsource/amiri/400.css";
import "@fontsource/amiri/700.css";
import "@fontsource/scheherazade-new/400.css";
import "@fontsource/scheherazade-new/700.css";
import "@fontsource/lateef/400.css";
import "@fontsource/lateef/700.css";

import "@/i18n";
import "./index.css";

import App from "./App.tsx";
import { store } from "@/app/store";
import {
  applyAccent,
  applyFont,
  applyThemeClass,
  syncSystemTheme,
  watchSystemTheme,
} from "@/features/ui/uiSlice";

// Reflect the stored preferences before the first paint, or the app flashes the defaults.
applyThemeClass(store.getState().ui.theme);
applyAccent(store.getState().ui.accent);
applyFont(store.getState().ui.font);
watchSystemTheme(() => store.dispatch(syncSystemTheme()));

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Provider store={store}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </Provider>
  </StrictMode>,
);
