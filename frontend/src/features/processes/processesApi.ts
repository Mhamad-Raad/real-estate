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

// A change to any step/entry/document re-fetches that process's detail AND the list (badges).
const touch = (id: number) => [
  { type: "Process" as const, id },
  { type: "Process" as const, id: "LIST" },
];

export const processesApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    listProcesses: builder.query<Paginated<ProcessListItem>, ProcessFilters>({
      query: (filters) => ({ url: "processes/", params: cleanFilters(filters) }),
      providesTags: [{ type: "Process", id: "LIST" }],
    }),
    getProcess: builder.query<ProcessDetail, number>({
      query: (id) => `processes/${id}/`,
      providesTags: (_r, _e, id) => [{ type: "Process", id }],
    }),
    createProcess: builder.mutation<ProcessListItem, ProcessCreateInput>({
      query: (body) => ({ url: "processes/", method: "POST", body }),
      invalidatesTags: [{ type: "Process", id: "LIST" }],
    }),
    deleteProcess: builder.mutation<void, number>({
      query: (id) => ({ url: `processes/${id}/`, method: "DELETE" }),
      invalidatesTags: [{ type: "Process", id: "LIST" }],
    }),
    updateProcess: builder.mutation<
      ProcessDetail,
      { id: number; version: number; lawyer_notes?: string; parcel?: number | null; category?: number | null }
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
      query: ({ id, process, ...body }) => ({
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
  useCompleteProcessMutation,
  useCreateEntryMutation,
  useUpdateEntryMutation,
  useDeleteEntryMutation,
} = processesApi;
