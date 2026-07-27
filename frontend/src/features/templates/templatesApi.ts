import { baseApi } from "@/services/baseApi";
import type { Paginated } from "@/services/types";

import type { DocumentTemplate, TemplateType } from "./types";

// Admin-managed .docx letter templates (§6.6). Uploading is multipart, so the body is FormData;
// everything else is ordinary JSON.
export const templatesApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    listTemplates: builder.query<Paginated<DocumentTemplate>, { page?: number }>({
      query: (params) => ({ url: "document-templates/", params }),
      providesTags: ["Template"],
    }),
    uploadTemplate: builder.mutation<
      DocumentTemplate,
      { template_type: TemplateType; name: string; file: File }
    >({
      query: ({ template_type, name, file }) => {
        const body = new FormData();
        body.append("template_type", template_type);
        body.append("name", name);
        body.append("file", file);
        return { url: "document-templates/", method: "POST", body };
      },
      invalidatesTags: ["Template"],
    }),
    activateTemplate: builder.mutation<DocumentTemplate, { id: number; version: number }>({
      query: ({ id, version }) => ({
        url: `document-templates/${id}/`,
        method: "PATCH",
        body: { is_active: true, version },
      }),
      invalidatesTags: ["Template"],
    }),
    deleteTemplate: builder.mutation<void, number>({
      query: (id) => ({ url: `document-templates/${id}/`, method: "DELETE" }),
      invalidatesTags: ["Template"],
    }),
  }),
});

export const {
  useListTemplatesQuery,
  useUploadTemplateMutation,
  useActivateTemplateMutation,
  useDeleteTemplateMutation,
} = templatesApi;
