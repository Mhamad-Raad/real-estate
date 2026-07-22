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
    // Used by the silent refresh-on-401 flow: swap the access token only.
    setAccess(state, action: PayloadAction<string>) {
      state.access = action.payload;
      localStorage.setItem(ACCESS_KEY, action.payload);
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
