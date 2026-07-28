import { baseApi } from "@/services/baseApi";
import { cleanParams } from "@/services/params";
import type { Paginated } from "@/services/types";

import type { Activity, ActivityFilters, ActivityVocabulary } from "./types";

export const activitiesApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    listActivities: builder.query<Paginated<Activity>, ActivityFilters>({
      query: (filters) => ({ url: "activities/", params: cleanParams(filters) }),
      providesTags: ["Activity"],
    }),
    getActivityVocabulary: builder.query<ActivityVocabulary, void>({
      query: () => ({ url: "activity-vocabulary/" }),
      providesTags: ["Activity"],
    }),
  }),
});

export const { useListActivitiesQuery, useGetActivityVocabularyQuery } = activitiesApi;
