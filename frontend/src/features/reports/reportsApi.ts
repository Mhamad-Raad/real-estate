import { PROCESS_LIST_TAG } from "@/features/processes/processesApi";
import { baseApi } from "@/services/baseApi";
import { cleanParams } from "@/services/params";

import type { ProcessReport, ReportFilters, UserReportRow } from "./types";

export const reportsApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getProcessReport: builder.query<ProcessReport, ReportFilters>({
      query: (filters) => ({ url: "reports/processes/", params: cleanParams(filters) }),
      providesTags: [PROCESS_LIST_TAG],
    }),
    getUserReport: builder.query<UserReportRow[], ReportFilters>({
      query: (filters) => ({ url: "reports/users/", params: cleanParams(filters) }),
      providesTags: [PROCESS_LIST_TAG],
    }),
  }),
});

export const { useGetProcessReportQuery, useGetUserReportQuery } = reportsApi;

/** CSV lives outside RTK Query: it's a file download, not cacheable server state. */
export function reportCsvUrl(kind: "processes" | "users", filters: ReportFilters): string {
  const params = new URLSearchParams({ ...cleanParams(filters), export: "csv" });
  return `/api/v1/reports/${kind}/?${params.toString()}`;
}
