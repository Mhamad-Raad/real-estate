import { baseApi } from "@/services/baseApi";
import type { Paginated } from "@/services/types";

import type { Activity, ActivityFilters, ActivityVocabulary } from "./types";

/** Drop blank filter values so they never reach the server as `?action=`. */
function cleanParams(filters: ActivityFilters): Record<string, string> {
  return Object.fromEntries(
    Object.entries(filters)
      .filter(([, value]) => value !== "" && value !== undefined && value !== null)
      .map(([key, value]) => [key, String(value)]),
  );
}

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
