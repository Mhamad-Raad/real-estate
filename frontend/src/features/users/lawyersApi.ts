import { baseApi } from "@/services/baseApi";

export interface Lawyer {
  id: number;
  username: string;
}

// Read-only assignable-user list for per-institute lawyer dropdowns (§5.1) — any authed user.
export const lawyersApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    listLawyers: builder.query<Lawyer[], void>({
      query: () => "lawyers/",
    }),
  }),
});

export const { useListLawyersQuery } = lawyersApi;
