export type OverallStatus = "draft" | "in_progress" | "complete" | "rejected";

export const OVERALL_STATUSES: OverallStatus[] = ["draft", "in_progress", "complete", "rejected"];

export interface ProcessListItem {
  id: number;
  client: number;
  client_full_name: string;
  client_pid: string;
  category: number | null;
  parcel: number | null;
  overall_status: OverallStatus;
  current_step: number;
  duplicate_flagged: boolean;
  assigned_lawyer: number;
  assigned_lawyer_username: string;
  created_at: string;
  version: number;
}

export interface ProcessCreateInput {
  client: number;
  parcel?: number | null;
  category?: number | null;
  assigned_lawyer?: number;
}

export interface ProcessFilters {
  search?: string;
  pid?: string;
  category?: number | "";
  overall_status?: OverallStatus | "";
  assigned_lawyer?: number | "";
  page?: number;
}

export type MatchReason = "pid" | "mother_name";
