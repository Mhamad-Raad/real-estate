import { baseApi } from "@/services/baseApi";
import type { Paginated } from "@/services/types";

import type {
  InstituteEntry,
  MatchReason,
  ProcessCreateInput,
  ProcessDetail,
  ProcessFilters,
  ProcessListItem,
  ProcessStep,
} from "./types";

// Strip empty filter values so we don't send `?category=` etc.
function cleanFilters(filters: ProcessFilters): Record<string, string | number> {
  return Object.fromEntries(
    Object.entries(filters).filter(([, v]) => v !== "" && v !== undefined && v !== null),
  ) as Record<string, string | number>;
}

/**
 * The tag every process write invalidates, and the one any process-derived query must provide.
 *
 * Exported because RTK Query does NOT match a bare `"Process"` tag against this id-scoped one:
 * a query tagged `["Process"]` never refetches after a case changes. The dashboard and reports
 * import this constant so the two sides cannot drift apart.
 */
export const PROCESS_LIST_TAG = { type: "Process" as const, id: "LIST" };

// A change to any step/entry/document re-fetches that process's detail AND the list (badges).
const touch = (id: number) => [{ type: "Process" as const, id }, PROCESS_LIST_TAG];

export const processesApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    listProcesses: builder.query<Paginated<ProcessListItem>, ProcessFilters>({
      query: (filters) => ({ url: "processes/", params: cleanFilters(filters) }),
      providesTags: [PROCESS_LIST_TAG],
    }),
    getProcess: builder.query<ProcessDetail, number>({
      query: (id) => `processes/${id}/`,
      providesTags: (_r, _e, id) => [{ type: "Process", id }],
    }),
    createProcess: builder.mutation<ProcessListItem, ProcessCreateInput>({
      query: (body) => ({ url: "processes/", method: "POST", body }),
      invalidatesTags: [PROCESS_LIST_TAG],
    }),
    deleteProcess: builder.mutation<void, number>({
      query: (id) => ({ url: `processes/${id}/`, method: "DELETE" }),
      invalidatesTags: [PROCESS_LIST_TAG],
    }),
    updateProcess: builder.mutation<
      ProcessDetail,
      {
        id: number;
        version: number;
        lawyer_notes?: string;
        land_id?: string;
        land_address?: string;
        category?: number | null;
      }
    >({
      query: ({ id, ...body }) => ({ url: `processes/${id}/`, method: "PATCH", body }),
      invalidatesTags: (_r, _e, arg) => touch(arg.id),
    }),
    overrideDuplicate: builder.mutation<
      ProcessListItem,
      { id: number; match_reason: MatchReason; reason: string; version: number }
    >({
      query: ({ id, ...body }) => ({
        url: `processes/${id}/override-duplicate/`,
        method: "POST",
        body,
      }),
      invalidatesTags: (_r, _e, arg) => touch(arg.id),
    }),

    // ---- 5-step workflow (§5) ----
    saveStep: builder.mutation<
      ProcessStep,
      { process: number; step: number; version: number } & Partial<ProcessStep>
    >({
      query: ({ process, step, ...body }) => ({
        url: `processes/${process}/steps/${step}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (_r, _e, arg) => touch(arg.process),
    }),
    // Explicit "proceed" — unlocks the next step for the lawyer (forward-only, server-side).
    advanceStep: builder.mutation<ProcessDetail, { id: number; version: number }>({
      query: ({ id, ...body }) => ({
        url: `processes/${id}/advance-step/`,
        method: "POST",
        body,
      }),
      invalidatesTags: (_r, _e, arg) => touch(arg.id),
    }),
    completeProcess: builder.mutation<
      ProcessDetail,
      { id: number; version: number; force?: boolean }
    >({
      query: ({ id, ...body }) => ({
        url: `processes/${id}/steps/5/complete/`,
        method: "POST",
        body,
      }),
      invalidatesTags: (_r, _e, arg) => touch(arg.id),
    }),

    // ---- Institute entries (Steps 2–4) ----
    createEntry: builder.mutation<InstituteEntry, Partial<InstituteEntry> & { process: number }>({
      query: (body) => ({ url: "institute-entries/", method: "POST", body }),
      invalidatesTags: (_r, _e, arg) => touch(arg.process),
    }),
    updateEntry: builder.mutation<
      InstituteEntry,
      { id: number; process: number; version: number } & Partial<InstituteEntry>
    >({
      query: ({ id, process: _process, ...body }) => ({
        url: `institute-entries/${id}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (_r, _e, arg) => touch(arg.process),
    }),
    deleteEntry: builder.mutation<void, { id: number; process: number }>({
      query: ({ id }) => ({ url: `institute-entries/${id}/`, method: "DELETE" }),
      invalidatesTags: (_r, _e, arg) => touch(arg.process),
    }),
  }),
});

export const {
  useListProcessesQuery,
  useGetProcessQuery,
  useCreateProcessMutation,
  useDeleteProcessMutation,
  useUpdateProcessMutation,
  useOverrideDuplicateMutation,
  useSaveStepMutation,
  useAdvanceStepMutation,
  useCompleteProcessMutation,
  useCreateEntryMutation,
  useUpdateEntryMutation,
  useDeleteEntryMutation,
} = processesApi;
