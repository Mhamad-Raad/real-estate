import { baseApi } from "@/services/baseApi";

export interface Health {
  status: string;
  /** The server's build. `app_version`/`build`, never `version` — that is the optimistic lock. */
  app_version: string;
  build: number;
}

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
