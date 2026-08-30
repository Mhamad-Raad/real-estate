import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

import type { User } from "./types";

const ACCESS_KEY = "access_token";
const REFRESH_KEY = "refresh_token";

/**
 * Tokens live in **sessionStorage**, not localStorage (It.8).
 *
 * These are shared office computers (§2). A refresh token is good for a week (UC-071), so a
 * `localStorage` copy meant that whoever opened the browser next morning was signed in as
 * yesterday's lawyer — with their menu, their cases and their name on every audited write.
 * `sessionStorage` keeps what UC-071 was actually about (a reload, or a navigation, must not
 * interrupt work) and drops what nobody asked for (surviving the machine being handed over).
 *
 * The cost is per-tab: a second tab signs in on its own. That is the price of the tab being the
 * unit of a session, and it is the cheap side of this trade.
 *
 * Not `httpOnly` cookies, which are the stronger answer to a *different* threat — a script
 * reading the token. This bundle has no third-party script, no CDN and no `innerHTML` sink, and
 * a cookie needs TLS to be worth setting, so that belongs with TLS in It.9 (§12).
 */
const store = sessionStorage;

// A token left by an older build would otherwise sit in localStorage for its full week, unread
// but still valid. Clear it once, on load.
localStorage.removeItem(ACCESS_KEY);
localStorage.removeItem(REFRESH_KEY);

interface AuthState {
  access: string | null;
  refresh: string | null;
  user: User | null;
}

const initialState: AuthState = {
  access: store.getItem(ACCESS_KEY),
  refresh: store.getItem(REFRESH_KEY),
  user: null,
};

const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    setCredentials(
      state,
      action: PayloadAction<{ access: string; refresh: string; user?: User }>,
    ) {
      state.access = action.payload.access;
      state.refresh = action.payload.refresh;
      if (action.payload.user) state.user = action.payload.user;
      store.setItem(ACCESS_KEY, action.payload.access);
      store.setItem(REFRESH_KEY, action.payload.refresh);
    },
    /** Used by the silent refresh-on-401 flow.
     *
     * The refresh token **rotates**: `ROTATE_REFRESH_TOKENS` issues a new one on every refresh and
     * `BLACKLIST_AFTER_ROTATION` blacklists the one just spent. Storing only the access token
     * therefore worked exactly once — the next silent refresh sent the blacklisted token, was
     * refused, and signed the user out mid-work about an hour in (UC-071). So whatever the server
     * hands back is kept, both halves.
     *
     * Deliberately a separate action from `setCredentials`: that one resets the RTK Query cache
     * (a different user is arriving), and a silent refresh must never do that — it happens
     * mid-session, under the same user, while their screens are showing data.
     */
    setAccess(state, action: PayloadAction<{ access: string; refresh?: string }>) {
      state.access = action.payload.access;
      store.setItem(ACCESS_KEY, action.payload.access);
      if (action.payload.refresh) {
        state.refresh = action.payload.refresh;
        store.setItem(REFRESH_KEY, action.payload.refresh);
      }
    },
    setUser(state, action: PayloadAction<User>) {
      state.user = action.payload;
    },
    logOut(state) {
      state.access = null;
      state.refresh = null;
      state.user = null;
      store.removeItem(ACCESS_KEY);
      store.removeItem(REFRESH_KEY);
    },
  },
});

export const { setCredentials, setAccess, setUser, logOut } = authSlice.actions;
export default authSlice.reducer;
