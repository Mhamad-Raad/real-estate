import { baseApi } from "@/services/baseApi";
import { cleanParams } from "@/services/params";
import type { Paginated } from "@/services/types";

import type {
  FastEntryInput,
  InstituteEntry,
  MatchReason,
  ProcessCreateInput,
  ProcessDetail,
  ProcessFilters,
  ProcessListItem,
  ProcessStep,
} from "./types";

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
      query: (filters) => ({ url: "processes/", params: cleanParams(filters) }),
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
    /** One finished paper allocation, in a single multipart request (UC-114).
     *
     * The office is carrying thousands of closed cases into the app and will not re-key five
     * steps of each: this sends the fields that make a case findable plus ONE PDF — the case
     * file, which is the same document step 5 compiles for a case worked here. */
    fastEntryProcess: builder.mutation<ProcessDetail, FastEntryInput>({
      query: ({ file, ...fields }) => {
        const form = new FormData();
        for (const [name, value] of Object.entries(fields)) form.append(name, String(value));
        form.append("file", file);
        return { url: "processes/fast-entry/", method: "POST", body: form };
      },
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
    /** Admin-only hand-over of a case. Assignment is open at creation, so a wrong name has to be
     *  fixable — no other endpoint can change `assigned_lawyer` (2026-08-06). */
    reassignProcess: builder.mutation<
      ProcessDetail,
      { id: number; assigned_lawyer: number; version: number }
    >({
      query: ({ id, ...body }) => ({ url: `processes/${id}/reassign/`, method: "POST", body }),
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
  useFastEntryProcessMutation,
  useDeleteProcessMutation,
  useUpdateProcessMutation,
  useOverrideDuplicateMutation,
  useReassignProcessMutation,
  useSaveStepMutation,
  useAdvanceStepMutation,
  useCompleteProcessMutation,
  useCreateEntryMutation,
  useUpdateEntryMutation,
  useDeleteEntryMutation,
} = processesApi;
