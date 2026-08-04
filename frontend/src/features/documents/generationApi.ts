import { baseApi } from "@/services/baseApi";

// Letter generation runs off the request path (§6.6): the endpoints return a job, and the UI
// polls it until it settles. Status lives in the database, not in Celery, so a restart or a
// reload never loses track of a run.
export type GenerationStatus = "pending" | "running" | "done" | "failed";

export interface GenerationJob {
  id: number;
  kind: "eligibility" | "process_list";
  status: GenerationStatus;
  template: number;
  process: number | null;
  process_ids: number[];
  document: number | null;
  error: string;
  requested_by: number;
  created_at: string;
}

export const isSettled = (status?: GenerationStatus) =>
  status === "done" || status === "failed";

export const generationApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    generateEligibility: builder.mutation<GenerationJob, { process: number }>({
      query: ({ process }) => ({
        url: `processes/${process}/generate-eligibility/`,
        method: "POST",
        body: {},
      }),
    }),
    generateProcessList: builder.mutation<GenerationJob, { process_ids: number[] }>({
      query: (body) => ({ url: "processes/generate-document/", method: "POST", body }),
    }),
    // The office's own code list — a different template with different columns, and a step gate
    // the list letter does not have, so it is its own endpoint rather than a mode of the other.
    generateProcessCodes: builder.mutation<GenerationJob, { process_ids: number[] }>({
      query: (body) => ({ url: "processes/generate-codes/", method: "POST", body }),
    }),
    compileCase: builder.mutation<GenerationJob, { process: number }>({
      query: ({ process }) => ({ url: `processes/${process}/compile/`, method: "POST", body: {} }),
    }),
    getGenerationJob: builder.query<GenerationJob, number>({
      query: (id) => `generation-jobs/${id}/`,
    }),
  }),
});

export const {
  useCompileCaseMutation,
  useGenerateEligibilityMutation,
  useGenerateProcessListMutation,
  useGenerateProcessCodesMutation,
  useGetGenerationJobQuery,
} = generationApi;
