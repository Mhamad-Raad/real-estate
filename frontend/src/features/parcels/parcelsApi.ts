import { baseApi } from "@/services/baseApi";
import type { Paginated } from "@/services/types";

export interface Parcel {
  id: number;
  parcel_number: string;
  location: string;
  version: number;
}

// Read-only here — parcels are reference data selected during process creation (§3.3).
export const parcelsApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    listParcels: builder.query<Paginated<Parcel>, void>({
      query: () => "parcels/",
      providesTags: ["Parcel"],
    }),
  }),
});

export const { useListParcelsQuery } = parcelsApi;
