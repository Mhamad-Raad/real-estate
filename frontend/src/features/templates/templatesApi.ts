import { baseApi } from "@/services/baseApi";
import type { Paginated } from "@/services/types";

import type { DocumentTemplate, TemplateTypeOption } from "./types";

// Letter templates are **read-only** over the API (§6.6, UC-010) — installed from the repo with
// `manage.py install_templates`, never uploaded from the running app. There is deliberately no
// upload/activate/delete mutation here: the server returns 405 for all three.
export const templatesApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    listTemplates: builder.query<Paginated<DocumentTemplate>, { page?: number }>({
      query: (params) => ({ url: "document-templates/", params }),
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
