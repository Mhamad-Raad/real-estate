import { baseApi } from "@/services/baseApi";

import type { DocumentMeta, UploadArgs } from "./types";

export const documentsApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    // Multipart upload — the parent process is re-fetched so step badges update (§3.6).
    uploadDocument: builder.mutation<DocumentMeta, UploadArgs>({
      query: ({ process, step_number, document_type, institute_entry, file }) => {
        const form = new FormData();
        form.append("process", String(process));
        form.append("step_number", String(step_number));
        form.append("document_type", document_type);
        if (institute_entry != null) form.append("institute_entry", String(institute_entry));
        form.append("file", file);
        return { url: "documents/", method: "POST", body: form };
      },
      invalidatesTags: (_r, _e, arg) => [
        { type: "Process", id: arg.process },
        { type: "Process", id: "LIST" },
      ],
    }),
    deleteDocument: builder.mutation<void, { id: number; process: number }>({
      query: ({ id }) => ({ url: `documents/${id}/`, method: "DELETE" }),
      invalidatesTags: (_r, _e, arg) => [
        { type: "Process", id: arg.process },
        { type: "Process", id: "LIST" },
      ],
    }),
  }),
});

export const { useUploadDocumentMutation, useDeleteDocumentMutation } = documentsApi;
