// The reading of one identity card (§6.5). Every field is a *candidate* the human confirms.

/** Which client column a card field lands in. `sex` is read for cross-checking only. */
export type DraftFieldName = "pid" | "full_name" | "mother_full_name" | "date_of_birth" | "sex";

export type DraftField = {
  value: string;
  /** 0–100, the engine's own confidence. Low means "look at this one closely". */
  confidence: number;
  /** Where it came from: the check-digit-verified MRZ, the printed front, or both agreeing. */
  source: "mrz" | "front" | "mrz+front" | "";
  /** A check digit or a cross-source agreement confirmed it — NOT that a person did. */
  verified: boolean;
};

export type CardDraft = {
  fields: Partial<Record<DraftFieldName, DraftField>>;
  warnings: string[];
};

export type ScanStatus = "pending" | "running" | "done" | "failed";

export type CardScan = {
  id: number;
  document_type: "ClientID" | "SpouseID";
  status: ScanStatus;
  draft: CardDraft;
  error: string;
  document: number | null;
  /** Who the confirmation created or updated — with the version the next call's lock needs. */
  client: number | null;
  client_version: number | null;
  /** The case the confirmation opened — the intake form navigates into its Step 1. */
  process: number | null;
  confirmed_at: string | null;
  confirmed_by: number | null;
  created_at: string;
};

/** What the human confirmed on screen. Optional throughout — a failed reading is typed by hand. */
export type ConfirmPayload = {
  pid?: string;
  full_name?: string;
  mother_full_name?: string;
  date_of_birth?: string | null;
  /** Absent → the card creates the client; present → it updates that one, under the version lock. */
  client?: number;
  client_version?: number;
  assigned_lawyer?: number | null;
  category?: number | null;
  // Only read when the card creates the case: the intake form asks for the land beside the card,
  // so it commits in the same transaction rather than a follow-up PATCH (§5).
  land_id?: string;
  land_address?: string;
  // Not on the card; typed beside it so the whole record is created in one place (UC-029/UC-030).
  place_of_birth?: string;
  address?: string;
  phone?: string;
  // Not on the card. Marital status decides whether Step 1 owes a spouse ID and whether the
  // letter prints a spouse row, and the letter needs the spouse's three printed fields together;
  // `spouse_pid` is never printed and exists only for the household duplicate rule (§5.7, §6.6).
  marital_status?: "single" | "married" | "divorced" | "widowed";
  spouse_name?: string;
  spouse_date_of_birth?: string | null;
  spouse_mother_full_name?: string;
  spouse_pid?: string;
};

export const isSettled = (status: ScanStatus) => status === "done" || status === "failed";

/** The fields the review form edits, in the order the card presents them. */
export const CARD_FIELDS = [
  "full_name",
  "pid",
  "mother_full_name",
  "date_of_birth",
] as const satisfies readonly DraftFieldName[];
