export interface LawyerCount {
  lawyer_id: number;
  username: string;
  count: number;
}

export interface DashboardStats {
  /** Rolling window, not a calendar week — see §10.1 / UC-001. */
  window_start: string;
  window_days: number;
  clients_in_window: number;
  processes_in_window: number;
  processes_total: number;
  /** Keyed by overall_status; every status is present, even at zero. */
  processes_by_status: Record<string, number>;
  /** Keyed by step number "1".."5". */
  processes_by_step: Record<string, number>;
  /** Distinct cases each user actually worked on in the window, from the audit log. */
  by_lawyer_handled: LawyerCount[];
  steps_missing_files: number;
  processes_missing_files: number;
  duplicate_flagged: number;
  similar_name_flagged: number;
}
