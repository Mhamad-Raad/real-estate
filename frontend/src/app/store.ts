import { configureStore, createListenerMiddleware, isAnyOf } from "@reduxjs/toolkit";

import { baseApi } from "@/services/baseApi";
import authReducer, { logOut, setCredentials } from "@/features/auth/authSlice";
import uiReducer from "@/features/ui/uiSlice";

// Every cached server response belongs to whoever was signed in when it was fetched, so signing
// out or signing in has to empty the cache — **not** just the tokens.
//
// Two office computers are shared between an admin and a lawyer (§2), and RTK Query survived the
// switch: the next user was served the previous one's `me`, so an admin who signed in after a
// lawyer saw the lawyer's menu and was bounced off the admin screens until they hit refresh. The
// same stale cache also held that user's clients, cases and activity rows.
//
// Wired here rather than in the reducer: `authSlice` cannot import `baseApi` (it is imported *by*
// it), and doing it in the store means it covers every way out — the sign-out button, an expired
// refresh token, and a 401 from any request.
const sessionListener = createListenerMiddleware();
sessionListener.startListening({
  matcher: isAnyOf(logOut, setCredentials),
  effect: async (_action, api) => {
    api.dispatch(baseApi.util.resetApiState());
  },
});

// RTK Query owns all server data; slices hold only global UI state (auth, theme/language).
export const store = configureStore({
  reducer: {
    [baseApi.reducerPath]: baseApi.reducer,
    auth: authReducer,
    ui: uiReducer,
  },
  middleware: (getDefault) =>
    getDefault().prepend(sessionListener.middleware).concat(baseApi.middleware),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
