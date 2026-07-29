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
};

export const isSettled = (status: ScanStatus) => status === "done" || status === "failed";

/** The fields the review form edits, in the order the card presents them. */
export const CARD_FIELDS = [
  "full_name",
  "pid",
  "mother_full_name",
  "date_of_birth",
] as const satisfies readonly DraftFieldName[];
