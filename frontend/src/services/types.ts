// DRF PageNumberPagination envelope — every list endpoint returns this shape.
export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// Matches the backend REST_FRAMEWORK PAGE_SIZE — used to compute page counts client-side.
export const PAGE_SIZE = 25;
