import { baseApi } from "@/services/baseApi";
import type { Paginated } from "@/services/types";

import type { Client, ClientInput, DuplicateCheckResult } from "./types";

export const clientsApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    listClients: builder.query<Paginated<Client>, { search?: string; pid?: string; page?: number }>({
      query: (params) => ({ url: "clients/", params }),
      providesTags: ["Client"],
    }),
    createClient: builder.mutation<Client, ClientInput>({
      query: (body) => ({ url: "clients/", method: "POST", body }),
      invalidatesTags: ["Client"],
    }),
    updateClient: builder.mutation<
      Client,
      { id: number; version: number } & Partial<ClientInput>
    >({
      query: ({ id, ...body }) => ({ url: `clients/${id}/`, method: "PATCH", body }),
      // Also Process: marital status and the spouse fields decide what Step 1 still requires,
      // so a stale process detail would show the wrong `missing` list (§3.6).
      invalidatesTags: ["Client", "Process"],
    }),
    deleteClient: builder.mutation<void, number>({
      query: (id) => ({ url: `clients/${id}/`, method: "DELETE" }),
      invalidatesTags: ["Client"],
    }),
    // Pre-save duplicate probe (§5.7): PID-exact and household (both hard) + mother-name fuzzy
    // (soft/sibling). `spouse_pid` is what the household check reads.
    checkDuplicate: builder.mutation<
      DuplicateCheckResult,
      { pid: string; mother_full_name: string; spouse_pid?: string; exclude_id?: number }
    >({
      query: (body) => ({ url: "clients/duplicate-check/", method: "POST", body }),
    }),
  }),
});

export const {
  useListClientsQuery,
  useCreateClientMutation,
  useUpdateClientMutation,
  useDeleteClientMutation,
  useCheckDuplicateMutation,
} = clientsApi;
