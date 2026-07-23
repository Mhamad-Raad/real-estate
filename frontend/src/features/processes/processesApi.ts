import { baseApi } from "@/services/baseApi";
import type { Paginated } from "@/services/types";

import type { MatchReason, ProcessCreateInput, ProcessFilters, ProcessListItem } from "./types";

// Strip empty filter values so we don't send `?category=` etc.
function cleanFilters(filters: ProcessFilters): Record<string, string | number> {
  return Object.fromEntries(
    Object.entries(filters).filter(([, v]) => v !== "" && v !== undefined && v !== null),
  ) as Record<string, string | number>;
}

export const processesApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    listProcesses: builder.query<Paginated<ProcessListItem>, ProcessFilters>({
      query: (filters) => ({ url: "processes/", params: cleanFilters(filters) }),
      providesTags: ["Process"],
    }),
    createProcess: builder.mutation<ProcessListItem, ProcessCreateInput>({
      query: (body) => ({ url: "processes/", method: "POST", body }),
      invalidatesTags: ["Process"],
    }),
    deleteProcess: builder.mutation<void, number>({
      query: (id) => ({ url: `processes/${id}/`, method: "DELETE" }),
      invalidatesTags: ["Process"],
    }),
    // Admin-only: clear a fired duplicate warning with a mandatory reason (§5.7). Sends `version`
    // for the optimistic lock; logged server-side in both DuplicateOverride and the audit trail.
    overrideDuplicate: builder.mutation<
      ProcessListItem,
      { id: number; match_reason: MatchReason; reason: string; version: number }
    >({
      query: ({ id, ...body }) => ({
        url: `processes/${id}/override-duplicate/`,
        method: "POST",
        body,
      }),
      invalidatesTags: ["Process"],
    }),
  }),
});

export const {
  useListProcessesQuery,
  useCreateProcessMutation,
  useDeleteProcessMutation,
  useOverrideDuplicateMutation,
} = processesApi;
