import { PROCESS_LIST_TAG } from "@/features/processes/processesApi";
import { baseApi } from "@/services/baseApi";

import type { DashboardStats } from "./types";

export const dashboardApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getDashboard: builder.query<DashboardStats, void>({
      query: () => ({ url: "dashboard/" }),
      // Shares the tag processesApi invalidates; a bare "Process" would never match it.
      providesTags: [PROCESS_LIST_TAG],
    }),
  }),
});

export const { useGetDashboardQuery } = dashboardApi;
