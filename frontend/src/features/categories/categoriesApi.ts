import { baseApi } from "@/services/baseApi";
import type { Paginated } from "@/services/types";

import type { Category, CategoryInput } from "./types";

export const categoriesApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    listCategories: builder.query<Paginated<Category>, void>({
      query: () => "categories/",
      providesTags: ["Category"],
    }),
    createCategory: builder.mutation<Category, CategoryInput>({
      query: (body) => ({ url: "categories/", method: "POST", body }),
      invalidatesTags: ["Category"],
    }),
    // `version` is the optimistic-lock token the server requires on every update.
    updateCategory: builder.mutation<
      Category,
      { id: number; version: number } & CategoryInput
    >({
      query: ({ id, ...body }) => ({ url: `categories/${id}/`, method: "PATCH", body }),
      invalidatesTags: ["Category"],
    }),
    deleteCategory: builder.mutation<void, number>({
      query: (id) => ({ url: `categories/${id}/`, method: "DELETE" }),
      invalidatesTags: ["Category"],
    }),
  }),
});

export const {
  useListCategoriesQuery,
  useCreateCategoryMutation,
  useUpdateCategoryMutation,
  useDeleteCategoryMutation,
} = categoriesApi;
