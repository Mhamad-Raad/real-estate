export interface ReportFilters {
  date_from?: string;
  date_to?: string;
  category?: number | "";
}

export interface CategoryCount {
  category_id: number | null;
  name: string;
  count: number;
}

export interface ProcessReport {
  total: number;
  by_status: Record<string, number>;
  by_step: Record<string, number>;
  by_category: CategoryCount[];
}

export interface UserReportRow {
  lawyer_id: number;
  username: string;
  assigned: number;
  in_progress: number;
  completed: number;
}
