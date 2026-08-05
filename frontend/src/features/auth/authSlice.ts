import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

import type { User } from "./types";

const ACCESS_KEY = "access_token";
const REFRESH_KEY = "refresh_token";

interface AuthState {
  access: string | null;
  refresh: string | null;
  user: User | null;
}

const initialState: AuthState = {
  access: localStorage.getItem(ACCESS_KEY),
  refresh: localStorage.getItem(REFRESH_KEY),
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
      localStorage.setItem(ACCESS_KEY, action.payload.access);
      localStorage.setItem(REFRESH_KEY, action.payload.refresh);
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
      localStorage.setItem(ACCESS_KEY, action.payload.access);
      if (action.payload.refresh) {
        state.refresh = action.payload.refresh;
        localStorage.setItem(REFRESH_KEY, action.payload.refresh);
      }
    },
    setUser(state, action: PayloadAction<User>) {
      state.user = action.payload;
    },
    logOut(state) {
      state.access = null;
      state.refresh = null;
      state.user = null;
      localStorage.removeItem(ACCESS_KEY);
      localStorage.removeItem(REFRESH_KEY);
    },
  },
});

export const { setCredentials, setAccess, setUser, logOut } = authSlice.actions;
export default authSlice.reducer;
