import { baseApi } from "@/services/baseApi";

import type { DashboardStats } from "./types";

export const dashboardApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getDashboard: builder.query<DashboardStats, void>({
      query: () => ({ url: "dashboard/" }),
      // Every figure is derived from processes, so any process write makes these stale.
      providesTags: ["Process"],
    }),
  }),
});

export const { useGetDashboardQuery } = dashboardApi;
