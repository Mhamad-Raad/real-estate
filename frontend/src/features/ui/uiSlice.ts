import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

/** What the user picked. `system` follows the OS, which is why it is stored separately. */
export const THEME_MODES = ["light", "dark", "system"] as const;
export type ThemeMode = (typeof THEME_MODES)[number];

/** What is actually on screen once `system` has been resolved. */
export type Theme = "light" | "dark";

const SYSTEM_DARK = "(prefers-color-scheme: dark)";

export function resolveTheme(mode: ThemeMode): Theme {
  if (mode !== "system") return mode;
  return window.matchMedia(SYSTEM_DARK).matches ? "dark" : "light";
}

// Reflect the theme onto <html class="dark"> so Tailwind's dark variant applies.
export function applyThemeClass(theme: Theme) {
  document.documentElement.classList.toggle("dark", theme === "dark");
}

/**
 * Full palettes — surfaces, borders and sidebar move with the accent, not just the buttons.
 * Ordered around the hue wheel so the settings grid reads as a spectrum; the CSS presets in
 * `index.css` key off these names.
 */
export const ACCENTS = [
  "teal",
  "emerald",
  "sky",
  "indigo",
  "violet",
  "rose",
  "copper",
  "amber",
  "slate",
] as const;
export type Accent = (typeof ACCENTS)[number];

/**
 * Selectable faces. **This is exactly the set that passed the glyph audit** — each one's shipped
 * woff2 files were read for the Sorani alphabet (ە ڕ ۆ ێ ڵ ڤ پ چ ژ گ) before being offered. Cairo,
 * Almarai, Tajawal, Changa and friends were candidates and were rejected for missing letters that
 * would render as tofu on a government document. All are bundled into `dist` (no CDN, §12).
 */
export const FONTS = [
  "vazirmatn",
  "noto",
  "plex",
  "naskh",
  "amiri",
  "scheherazade",
  "notokufi",
  "reemkufi",
  "lateef",
] as const;
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
  /** The user's choice, including `system`. */
  mode: ThemeMode;
  /** The resolved light/dark actually rendered — what the rest of the app reads. */
  theme: Theme;
  sidebarCollapsed: boolean;
  accent: Accent;
  font: FontChoice;
}

// The key predates `system` and held "light"/"dark"; both are still valid modes, so old machines
// carry their choice over untouched.
const initialMode = stored("theme", THEME_MODES, "system");

const uiSlice = createSlice({
  name: "ui",
  initialState: {
    mode: initialMode,
    theme: resolveTheme(initialMode),
    sidebarCollapsed: initialSidebarCollapsed(),
    accent: stored("accent", ACCENTS, "teal"),
    font: stored("font", FONTS, "vazirmatn"),
  } as UiState,
  reducers: {
    setThemeMode(state, action: PayloadAction<ThemeMode>) {
      state.mode = action.payload;
      state.theme = resolveTheme(action.payload);
      localStorage.setItem("theme", action.payload);
      applyThemeClass(state.theme);
    },
    // The header button is a plain light/dark switch: it commits to what the user can see, which
    // means stepping off `system` rather than toggling within it.
    toggleTheme(state) {
      state.mode = state.theme === "dark" ? "light" : "dark";
      state.theme = state.mode;
      localStorage.setItem("theme", state.mode);
      applyThemeClass(state.theme);
    },
    // Fired by the OS media-query listener; only `system` follows it.
    syncSystemTheme(state) {
      if (state.mode !== "system") return;
      state.theme = resolveTheme("system");
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

export const { setThemeMode, toggleTheme, syncSystemTheme, toggleSidebar, setAccent, setFont } =
  uiSlice.actions;
export default uiSlice.reducer;

/** Keep `system` honest while the app is open — the OS can flip at sunset. */
export function watchSystemTheme(onChange: () => void) {
  window.matchMedia(SYSTEM_DARK).addEventListener("change", onChange);
}
