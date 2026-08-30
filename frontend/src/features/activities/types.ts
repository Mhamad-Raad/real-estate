export type ActivityAction =
  | "create"
  | "update"
  | "delete"
  | "restore"
  | "verify"
  | "override"
  | "generate"
  | "login"
  | "logout";

export interface Activity {
  id: number;
  actor: number | null;
  actor_username: string;
  action: ActivityAction;
  entity_type: string;
  entity_id: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

export interface ActivityFilters {
  actor?: string;
  action?: string;
  entity_type?: string;
  created_after?: string;
  created_before?: string;
  page?: number;
}

export interface ActivityVocabulary {
  actions: { value: string; label: string }[];
  entity_types: string[];
  /** From the log itself, so a deactivated user with history is still filterable. */
  actors: { id: number; username: string }[];
}
