import { bilingualLabel } from "@/lib/bilingual";
import { baseApi } from "@/services/baseApi";

// The shared controlled document-type vocabulary (§6.7) — read-only, never hard-coded on the
// client. Keeps the upload slots in step with what the backend requires for completion.
export interface DocumentType {
  code: string;
  display_key: string; // i18n key; label comes from the translation files
  step: number | null; // null = not tied to one step (e.g. the generic institute document)
  required: boolean;
  only_when_married: boolean; // e.g. the spouse ID — no spouse, no slot
  generated: boolean; // produced by the system — shown as output, never an upload slot
  // The slot's capacity, refused past (UC-085). Still not a *completion* rule in the other
  // direction: a card with one side on file is present, and no step is blocked on the second.
  expected_parts: number;
  // What a "part" is. An identity card stores BOTH sides as one document, so its slot counts
  // pages and says "sides" — counting rows reported a complete card as "1 of 2 files" (UC-083).
  counts_pages: boolean;
  name_ckb: string;
  // Set only for a paper the office knows by both names; blank means one label is enough.
  name_en: string;
}

/** What a slot is called. A paper with an English name of its own prints the pair (UC-088) —
 * English first here, because that is the order the office asked for on this screen. */
export function documentTypeLabel(
  type: Pick<DocumentType, "name_ckb" | "name_en">,
  fallback: string,
): string {
  return type.name_en ? bilingualLabel(type.name_en, type.name_ckb) : fallback;
}

export const documentTypesApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    listDocumentTypes: builder.query<DocumentType[], void>({
      query: () => "document-types/",
    }),
  }),
});

export const { useListDocumentTypesQuery } = documentTypesApi;
