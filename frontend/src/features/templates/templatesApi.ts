import { baseApi } from "@/services/baseApi";
import type { DocumentTemplate, TemplateTypeOption } from "./types";

// Letter templates are **read-only** over the API (§6.6, UC-010) — installed from the repo with
// `manage.py install_templates`, never uploaded from the running app. There is deliberately no
// upload/activate/delete mutation here: the server returns 405 for all three.
export const templatesApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    // Unpaginated (see the viewset): the screen groups by letter type, and a grouping split
    // across pages would render a type as "none installed" while its active row sat on page 2.
    listTemplates: builder.query<DocumentTemplate[], void>({
      query: () => "document-templates/",
      providesTags: ["Template"],
    }),
    // The vocabulary the backend owns. Fetched rather than hard-coded because three frontend
    // copies of it fell a whole type behind when `case_summary` was added (UC-008).
    listTemplateTypes: builder.query<TemplateTypeOption[], void>({
      query: () => "template-types/",
    }),
  }),
});

export const { useListTemplatesQuery, useListTemplateTypesQuery } = templatesApi;
