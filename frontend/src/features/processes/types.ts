import type { ClientInput } from "@/features/clients/types";

export type OverallStatus = "draft" | "in_progress" | "complete" | "rejected";

export const OVERALL_STATUSES: OverallStatus[] = ["draft", "in_progress", "complete", "rejected"];

/** The workflow's step numbers — the client-side half of `processes/constants.py` (§5).
 *
 * Two screens spelled `[1, 2, 3, 4, 5]` out by hand, which is two more places to find when the
 * office's seven steps land (UC-043).
 */
export const STEP_NUMBERS = [1, 2, 3, 4, 5] as const;

export interface ProcessListItem {
  id: number;
  client: number;
  client_full_name: string;
  client_pid: string;
  category: number | null;
  // The office's case number (`A102`), issued by the system at creation and never editable
  // (§3.8, UC-064). Empty only for a case opened without a category.
  unique_code: string;
  land_id: string;
  land_address: string;
  overall_status: OverallStatus;
  current_step: number;
  duplicate_flagged: boolean;
  similar_name_flagged: boolean;
  // Typed in through the fast-entry form rather than worked through the five steps (UC-114). The
  // screens badge it so the empty steps read as history, not as work nobody finished.
  fast_entry: boolean;
  assigned_lawyer: number;
  assigned_lawyer_username: string;
  created_at: string;
  // Only ever present on the restore desk's listing (UC-063); a live case has none.
  deleted_at?: string | null;
  version: number;
}

/**
 * The Step-1 intake payload (§5, UC-024). Exactly one of `client` (already on file) or
 * `client_data` (created by this same submit) — the server rejects both or neither.
 */
export interface ProcessCreateInput {
  client?: number;
  client_data?: ClientInput;
  category?: number | null;
  assigned_lawyer?: number;
  land_id?: string;
  land_address?: string;
}

export interface ProcessFilters {
  search?: string;
  pid?: string;
  category?: number | "";
  overall_status?: OverallStatus | "";
  assigned_lawyer?: number | "";
  current_step?: number | "";
  page?: number;
}

export type MatchReason = "pid" | "mother_name";

// ---- Process detail / 5-step workflow (§5) ----

export type StepStatus = "not_started" | "in_progress" | "missing" | "complete";
export type ApprovalStatus = "pending" | "approved" | "rejected";

export interface ProcessStep {
  id: number;
  step_number: number;
  status: StepStatus;
  start_date: string | null;
  end_date: string | null;
  out_of_city_flag: boolean;
  // Server-computed codes for what this step still needs: `institute:<code>`, `doc:<type>`,
  // `step:<n>`, or a bare field name. Empty means complete.
  missing: string[];
  version: number;
}

export interface InstituteEntry {
  id: number;
  process: number;
  step_number: number;
  institute_code: string;
  is_custom: boolean;
  custom_name: string;
  assigned_lawyer: number | null;
  approval_status: ApprovalStatus;
  approval_date: string | null;
  version: number;
}

export interface StepStatusSummary {
  steps: Record<string, StepStatus>;
  completed: number;
  total: number;
}

export interface ProcessDetail extends ProcessListItem {
  lawyer_notes: string;
  steps: ProcessStep[];
  institute_entries: InstituteEntry[];
  step_status_summary: StepStatusSummary;
  documents: import("@/features/documents/types").DocumentMeta[];
  client_detail: import("@/features/clients/types").Client;
}


/** What the fast-entry form sends (UC-114): the fields that make a case findable, plus the one
 *  PDF that stands in for the whole file. Everything else on the case stays empty on purpose. */
export interface FastEntryInput {
  full_name: string;
  pid: string;
  mother_full_name: string;
  date_of_birth: string;
  category: number | string;
  land_id: string;
  mark_complete: boolean;
  file: File;
}
