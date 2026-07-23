// DRF PageNumberPagination envelope — every list endpoint returns this shape.
export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
