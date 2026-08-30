import {
  createApi,
  fetchBaseQuery,
  type BaseQueryFn,
  type FetchArgs,
  type FetchBaseQueryError,
} from "@reduxjs/toolkit/query/react";
import { Mutex } from "async-mutex";

import type { RootState } from "@/app/store";
import { logOut, setAccess } from "@/features/auth/authSlice";

const rawBaseQuery = fetchBaseQuery({
  baseUrl: "/api/v1/",
  prepareHeaders: (headers, { getState }) => {
    const token = (getState() as RootState).auth.access;
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return headers;
  },
});

// Serialize refreshes so a burst of 401s triggers exactly one refresh call.
const refreshMutex = new Mutex();

// On 401, silently refresh the access token once and retry; on failure, log out.
const baseQueryWithReauth: BaseQueryFn<
  string | FetchArgs,
  unknown,
  FetchBaseQueryError
> = async (args, api, extraOptions) => {
  await refreshMutex.waitForUnlock();
  let result = await rawBaseQuery(args, api, extraOptions);

  if (result.error?.status === 401) {
    const refresh = (api.getState() as RootState).auth.refresh;
    if (!refresh) {
      api.dispatch(logOut());
      return result;
    }
    if (!refreshMutex.isLocked()) {
      const release = await refreshMutex.acquire();
      try {
        const refreshResult = await rawBaseQuery(
          { url: "auth/refresh/", method: "POST", body: { refresh } },
          api,
          extraOptions,
        );
        // Both halves: the refresh token rotates, and the one just spent is blacklisted (UC-071).
        const data = refreshResult.data as { access?: string; refresh?: string } | undefined;
        if (data?.access) {
          api.dispatch(setAccess({ access: data.access, refresh: data.refresh }));
          result = await rawBaseQuery(args, api, extraOptions);
        } else {
          api.dispatch(logOut());
        }
      } finally {
        release();
      }
    } else {
      await refreshMutex.waitForUnlock();
      result = await rawBaseQuery(args, api, extraOptions);
    }
  }
  return result;
};

export const baseApi = createApi({
  reducerPath: "api",
  baseQuery: baseQueryWithReauth,
  tagTypes: ["User", "Process", "Client", "Activity", "Category", "Template"],
  endpoints: () => ({}),
});
