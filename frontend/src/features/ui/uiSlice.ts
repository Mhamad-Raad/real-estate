import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

export type Theme = "light" | "dark";

function initialTheme(): Theme {
  const stored = localStorage.getItem("theme");
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

// Reflect the theme onto <html class="dark"> so Tailwind's dark variant applies.
export function applyThemeClass(theme: Theme) {
  document.documentElement.classList.toggle("dark", theme === "dark");
}

/** Accent presets — pure CSS token overrides, so these cost bytes rather than a font payload. */
export const ACCENTS = [
  "teal", "blue", "indigo", "violet", "rose",
  "amber", "green", "emerald", "slate", "graphite",
] as const;
export type Accent = (typeof ACCENTS)[number];

/**
 * Selectable Arabic faces. **Short on purpose** — every one is bundled into `dist` (no CDN, §12)
 * and every one was verified glyph-by-glyph against the Sorani alphabet first. Cairo was a
 * candidate and was rejected: it lacks ە ڕ ۆ ێ ڵ, which render as tofu on a government document.
 */
export const FONTS = ["vazirmatn", "noto", "lateef", "reemkufi"] as const;
export type FontChoice = (typeof FONTS)[number];

// Applied as data attributes on <html>; the presets in index.css key off them.
export function applyAccent(accent: Accent) {
  document.documentElement.dataset.accent = accent;
}

export function applyFont(font: FontChoice) {
  document.documentElement.dataset.font = font;
}

function stored<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  const value = localStorage.getItem(key) as T | null;
  return value && allowed.includes(value) ? value : fallback;
}

// A sidebar that re-expands on every navigation is worse than none, so the choice persists —
// legitimate global UI state per §14.3, alongside theme and language (UC-007).
function initialSidebarCollapsed(): boolean {
  return localStorage.getItem("sidebar_collapsed") === "true";
}

interface UiState {
  theme: Theme;
  sidebarCollapsed: boolean;
  accent: Accent;
  font: FontChoice;
}

const uiSlice = createSlice({
  name: "ui",
  initialState: {
    theme: initialTheme(),
    sidebarCollapsed: initialSidebarCollapsed(),
    accent: stored("accent", ACCENTS, "teal"),
    font: stored("font", FONTS, "vazirmatn"),
  } as UiState,
  reducers: {
    setTheme(state, action: PayloadAction<Theme>) {
      state.theme = action.payload;
      localStorage.setItem("theme", action.payload);
      applyThemeClass(action.payload);
    },
    toggleTheme(state) {
      state.theme = state.theme === "dark" ? "light" : "dark";
      localStorage.setItem("theme", state.theme);
      applyThemeClass(state.theme);
    },
    toggleSidebar(state) {
      state.sidebarCollapsed = !state.sidebarCollapsed;
      localStorage.setItem("sidebar_collapsed", String(state.sidebarCollapsed));
    },
    setAccent(state, action: PayloadAction<Accent>) {
      state.accent = action.payload;
      localStorage.setItem("accent", action.payload);
      applyAccent(action.payload);
    },
    setFont(state, action: PayloadAction<FontChoice>) {
      state.font = action.payload;
      localStorage.setItem("font", action.payload);
      applyFont(action.payload);
    },
  },
});

export const { setTheme, toggleTheme, toggleSidebar, setAccent, setFont } = uiSlice.actions;
export default uiSlice.reducer;
