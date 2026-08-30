import { bilingualLabel } from "@/lib/bilingual";
import { baseApi } from "@/services/baseApi";

// The shared Step 2–4 institute enum (§3.4) — read-only, never hard-coded on the client.
export interface Institute {
  code: string;
  display_key: string; // i18n key; label comes from the translation files
  step: number;
  name_ckb: string;
  name_en: string;
}

/**
 * A case screen names an institute in **both** languages at once (UC-054) — Kurdish first, which
 * is the name on the paper. The compiled cover sheet keeps the Kurdish name alone; its table has
 * no room for both. See `bilingualLabel` for why the pair is not translated.
 */
export function instituteLabel(institute: Pick<Institute, "name_ckb" | "name_en">): string {
  return bilingualLabel(institute.name_ckb, institute.name_en);
}

export const institutesApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    listInstitutes: builder.query<Institute[], void>({
      query: () => "institutes/",
    }),
  }),
});

export const { useListInstitutesQuery } = institutesApi;
