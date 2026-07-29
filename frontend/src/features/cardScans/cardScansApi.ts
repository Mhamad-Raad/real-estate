import { baseApi } from "@/services/baseApi";
import { PROCESS_LIST_TAG } from "@/features/processes/processesApi";

import type { CardScan, ConfirmPayload } from "./types";

export const cardScansApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    // Both sides go up together and the server merges them into one PDF — a card is one
    // document, and the reader needs both sides to cross-check the number (§6.2).
    stageCardScan: builder.mutation<
      CardScan,
      { document_type: string; front: File; back?: File | null }
    >({
      query: ({ document_type, front, back }) => {
        const form = new FormData();
        form.append("document_type", document_type);
        form.append("file", front);
        if (back) form.append("back", back);
        return { url: "card-scans/", method: "POST", body: form };
      },
    }),

    getCardScan: builder.query<CardScan, number>({
      query: (id) => `card-scans/${id}/`,
    }),

    // Confirmation creates the client, the case and the filed document, so every list that
    // shows any of them is now stale (§6.5). `"Client"` is deliberately the bare tag that
    // `clientsApi` provides — an id-scoped one would silently fail to match it.
    confirmCardScan: builder.mutation<CardScan, { id: number } & ConfirmPayload>({
      query: ({ id, ...body }) => ({ url: `card-scans/${id}/confirm/`, method: "POST", body }),
      invalidatesTags: ["Client", PROCESS_LIST_TAG],
    }),
  }),
});

export const {
  useStageCardScanMutation,
  useGetCardScanQuery,
  useLazyGetCardScanQuery,
  useConfirmCardScanMutation,
} = cardScansApi;
