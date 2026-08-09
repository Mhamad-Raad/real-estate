import { baseApi } from "@/services/baseApi";
import type { Health } from "./types";

export const systemApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    // Untagged on purpose: the build cannot change while the page is open, so there is nothing
    // to invalidate. It is fetched once per app load.
    getHealth: builder.query<Health, void>({
      query: () => "health/",
    }),
  }),
});

export const { useGetHealthQuery } = systemApi;
