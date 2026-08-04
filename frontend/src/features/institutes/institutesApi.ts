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
 * A case screen names an institute in **both** languages at once (UC-054), because the office
 * deals with bodies that are known by their Kurdish name on paper and their English one in the
 * ministry's own correspondence. Deliberately not localised: the pair is the same in every
 * interface language, which is why it is served with the institute rather than translated.
 * The compiled cover sheet keeps the Kurdish name alone — its table has no room for both.
 */
export function instituteLabel(institute: Pick<Institute, "name_ckb" | "name_en">): string {
  const { name_ckb: ckb, name_en: en } = institute;
  if (!ckb || !en || ckb === en) return ckb || en;
  return `${ckb} — ${en}`;
}

export const institutesApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    listInstitutes: builder.query<Institute[], void>({
      query: () => "institutes/",
    }),
  }),
});

export const { useListInstitutesQuery } = institutesApi;
