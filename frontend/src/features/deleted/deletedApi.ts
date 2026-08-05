import type { Client } from "@/features/clients/types";
import { PROCESS_LIST_TAG } from "@/features/processes/processesApi";
import type { ProcessListItem } from "@/features/processes/types";
import { baseApi } from "@/services/baseApi";
import type { Paginated } from "@/services/types";

/**
 * The admin restore desk (UC-063). Nothing here is ever hard-deleted (§11.1), so every soft-delete
 * viewset exposes the same pair — `GET <resource>/deleted/` to see them and `POST <id>/restore/`
 * to bring one back, both admin-only.
 *
 * Restoring a case invalidates **both** lists: the beneficiary comes back with it (UC-061), so a
 * restore made from the cases tab silently changes the clients tab too.
 */
export const deletedApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    listDeletedProcesses: builder.query<Paginated<ProcessListItem> | ProcessListItem[], void>({
      query: () => "processes/deleted/",
      providesTags: [PROCESS_LIST_TAG],
    }),
    listDeletedClients: builder.query<Paginated<Client> | Client[], void>({
      query: () => "clients/deleted/",
      providesTags: ["Client"],
    }),
    restoreProcess: builder.mutation<ProcessListItem, number>({
      query: (id) => ({ url: `processes/${id}/restore/`, method: "POST" }),
      invalidatesTags: [PROCESS_LIST_TAG, "Client"],
    }),
    restoreClient: builder.mutation<Client, number>({
      query: (id) => ({ url: `clients/${id}/restore/`, method: "POST" }),
      invalidatesTags: ["Client", PROCESS_LIST_TAG],
    }),
  }),
});

export const {
  useListDeletedProcessesQuery,
  useListDeletedClientsQuery,
  useRestoreProcessMutation,
  useRestoreClientMutation,
} = deletedApi;
