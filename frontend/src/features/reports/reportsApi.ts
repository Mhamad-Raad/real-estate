import { baseApi } from "@/services/baseApi";

import type { ProcessReport, ReportFilters, UserReportRow } from "./types";

/** Drop empty filter values so they never reach the server as `?category=`. */
function cleanParams(filters: ReportFilters): Record<string, string> {
  return Object.fromEntries(
    Object.entries(filters)
      .filter(([, value]) => value !== "" && value !== undefined && value !== null)
      .map(([key, value]) => [key, String(value)]),
  );
}

export const reportsApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getProcessReport: builder.query<ProcessReport, ReportFilters>({
      query: (filters) => ({ url: "reports/processes/", params: cleanParams(filters) }),
      providesTags: ["Process"],
    }),
    getUserReport: builder.query<UserReportRow[], ReportFilters>({
      query: (filters) => ({ url: "reports/users/", params: cleanParams(filters) }),
      providesTags: ["Process"],
    }),
  }),
});

export const { useGetProcessReportQuery, useGetUserReportQuery } = reportsApi;

/** CSV lives outside RTK Query: it's a file download, not cacheable server state. */
export function reportCsvUrl(kind: "processes" | "users", filters: ReportFilters): string {
  const params = new URLSearchParams({ ...cleanParams(filters), export: "csv" });
  return `/api/v1/reports/${kind}/?${params.toString()}`;
}
