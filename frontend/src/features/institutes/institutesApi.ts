import { baseApi } from "@/services/baseApi";

// The shared Step 2–4 institute enum (§3.4) — read-only, never hard-coded on the client.
export interface Institute {
  code: string;
  display_key: string; // i18n key; label comes from the translation files
  step: number;
}

export const institutesApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    listInstitutes: builder.query<Institute[], void>({
      query: () => "institutes/",
    }),
  }),
});

export const { useListInstitutesQuery } = institutesApi;
