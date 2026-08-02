import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Provider } from "react-redux";
import { BrowserRouter } from "react-router-dom";

// Bundled offline fonts (no CDN) — Vazirmatn for Arabic/Kurdish, Inter for Latin.
import "@fontsource-variable/vazirmatn";
import "@fontsource-variable/inter";
// Selectable Arabic faces (UC-015). Each was verified to cover the Sorani letters before being
// offered; all are bundled, because the app runs with no internet at all (§12).
import "@fontsource-variable/noto-sans-arabic";
import "@fontsource-variable/reem-kufi";
import "@fontsource/lateef";

import "@/i18n";
import "./index.css";

import App from "./App.tsx";
import { store } from "@/app/store";
import { applyAccent, applyFont, applyThemeClass } from "@/features/ui/uiSlice";

// Reflect the stored preferences before the first paint, or the app flashes the defaults.
applyThemeClass(store.getState().ui.theme);
applyAccent(store.getState().ui.accent);
applyFont(store.getState().ui.font);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Provider store={store}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </Provider>
  </StrictMode>,
);
