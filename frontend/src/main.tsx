import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Provider } from "react-redux";
import { BrowserRouter } from "react-router-dom";

// Bundled offline fonts (no CDN) — Vazirmatn for Arabic/Kurdish, Inter for Latin.
import "@fontsource-variable/vazirmatn";
import "@fontsource-variable/inter";

import "@/i18n";
import "./index.css";

import App from "./App.tsx";
import { store } from "@/app/store";
import { applyThemeClass } from "@/features/ui/uiSlice";

// Apply the persisted theme before first paint to avoid a light/dark flash.
applyThemeClass(store.getState().ui.theme);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Provider store={store}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </Provider>
  </StrictMode>,
);
