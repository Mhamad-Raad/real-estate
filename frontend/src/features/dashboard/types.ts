export interface LawyerCount {
  lawyer_id: number;
  username: string;
  count: number;
}

export interface DashboardStats {
  week_start: string;
  clients_this_week: number;
  processes_this_week: number;
  processes_total: number;
  /** Keyed by overall_status; every status is present, even at zero. */
  processes_by_status: Record<string, number>;
  /** Keyed by step number "1".."5". */
  processes_by_step: Record<string, number>;
  by_lawyer_this_week: LawyerCount[];
  steps_missing_files: number;
  processes_missing_files: number;
  duplicate_flagged: number;
  similar_name_flagged: number;
}
