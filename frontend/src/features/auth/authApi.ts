import { baseApi } from "@/services/baseApi";

import type { LoginRequest, LoginResponse, User } from "./types";

// Auth server interactions live in RTK Query; the slice only holds the resulting tokens/user.
export const authApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    login: builder.mutation<LoginResponse, LoginRequest>({
      query: (body) => ({ url: "auth/login/", method: "POST", body }),
    }),
    me: builder.query<User, void>({
      query: () => "auth/me/",
      providesTags: ["User"],
    }),
    updatePreferences: builder.mutation<User, Partial<Pick<User, "language" | "theme">>>({
      query: (body) => ({ url: "auth/me/", method: "PATCH", body }),
      invalidatesTags: ["User"],
    }),
    logout: builder.mutation<void, { refresh: string }>({
      query: (body) => ({ url: "auth/logout/", method: "POST", body }),
    }),
  }),
});

export const {
  useLoginMutation,
  useMeQuery,
  useUpdatePreferencesMutation,
  useLogoutMutation,
} = authApi;
