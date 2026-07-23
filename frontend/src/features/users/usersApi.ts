import { baseApi } from "@/services/baseApi";
import type { Paginated } from "@/services/types";

import type { AdminUser, UserCreateInput, UserUpdateInput } from "./types";

export const usersApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    listUsers: builder.query<Paginated<AdminUser>, void>({
      query: () => "users/",
      providesTags: ["User"],
    }),
    createUser: builder.mutation<AdminUser, UserCreateInput>({
      query: (body) => ({ url: "users/", method: "POST", body }),
      invalidatesTags: ["User"],
    }),
    updateUser: builder.mutation<AdminUser, UserUpdateInput>({
      query: ({ id, ...body }) => ({ url: `users/${id}/`, method: "PATCH", body }),
      invalidatesTags: ["User"],
    }),
    deleteUser: builder.mutation<void, number>({
      query: (id) => ({ url: `users/${id}/`, method: "DELETE" }),
      invalidatesTags: ["User"],
    }),
    restoreUser: builder.mutation<AdminUser, number>({
      query: (id) => ({ url: `users/${id}/restore/`, method: "POST" }),
      invalidatesTags: ["User"],
    }),
  }),
});

export const {
  useListUsersQuery,
  useCreateUserMutation,
  useUpdateUserMutation,
  useDeleteUserMutation,
} = usersApi;
