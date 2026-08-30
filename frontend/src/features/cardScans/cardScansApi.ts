import { baseApi } from "@/services/baseApi";
import { PROCESS_LIST_TAG } from "@/features/processes/processesApi";

import type { CardScan, ConfirmPayload } from "./types";

/** Exported so the tag set can be asserted directly — a behavioural RTK Query test is not viable
 *  here (`baseUrl` is relative and Node's `Request` rejects that, even under jsdom). */
export function confirmInvalidates(result?: CardScan) {
  const tags = ["Client" as const, PROCESS_LIST_TAG];
  return result?.process ? [...tags, { type: "Process" as const, id: result.process }] : tags;
}

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
    //
    // The **id-scoped** process tag matters just as much and in the opposite direction: the
    // detail query provides `{type:'Process', id}`, and `PROCESS_LIST_TAG` is `id:'LIST'`, which
    // does not match it. Filing a spouse card onto an open case (UC-048) would otherwise leave
    // Step 1 still reporting the spouse ID missing until the page was reloaded — the silent
    // stale-cache class this project already hit once in It.4.
    confirmCardScan: builder.mutation<CardScan, { id: number } & ConfirmPayload>({
      query: ({ id, ...body }) => ({ url: `card-scans/${id}/confirm/`, method: "POST", body }),
      invalidatesTags: confirmInvalidates,
    }),
  }),
});

export const {
  useStageCardScanMutation,
  useGetCardScanQuery,
  useConfirmCardScanMutation,
} = cardScansApi;
