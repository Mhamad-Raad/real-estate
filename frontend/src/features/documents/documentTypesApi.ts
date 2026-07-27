import { baseApi } from "@/services/baseApi";

// The shared controlled document-type vocabulary (§6.7) — read-only, never hard-coded on the
// client. Keeps the upload slots in step with what the backend requires for completion.
export interface DocumentType {
  code: string;
  display_key: string; // i18n key; label comes from the translation files
  step: number | null; // null = not tied to one step (e.g. the generic institute document)
  required: boolean;
  only_when_married: boolean; // e.g. the spouse ID — no spouse, no slot
}

export const documentTypesApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    listDocumentTypes: builder.query<DocumentType[], void>({
      query: () => "document-types/",
    }),
  }),
});

export const { useListDocumentTypesQuery } = documentTypesApi;
