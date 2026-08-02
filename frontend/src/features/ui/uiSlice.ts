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

// A sidebar that re-expands on every navigation is worse than none, so the choice persists —
// legitimate global UI state per §14.3, alongside theme and language (UC-007).
function initialSidebarCollapsed(): boolean {
  return localStorage.getItem("sidebar_collapsed") === "true";
}

interface UiState {
  theme: Theme;
  sidebarCollapsed: boolean;
}

const uiSlice = createSlice({
  name: "ui",
  initialState: { theme: initialTheme(), sidebarCollapsed: initialSidebarCollapsed() } as UiState,
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
  },
});

export const { setTheme, toggleTheme, toggleSidebar } = uiSlice.actions;
export default uiSlice.reducer;
