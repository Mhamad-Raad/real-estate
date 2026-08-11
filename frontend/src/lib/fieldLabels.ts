import type { TFunction } from "i18next";

/** API field name → the i18n key the screens already label that input with.
 *
 * So a rejected save can say *which* field it was about. The server answers in English with the
 * machine name (`date_of_birth`), and every screen in this app is localized (§9) — printing the
 * raw key at the user would be the `INST_S4_B` mistake again.
 *
 * One map rather than one per feature: these names are the API's, and the same `phone` or
 * `land_id` is posted from several screens. A field missing here simply goes unlabelled — the
 * message still shows, it just does not name the input, so an omission degrades quietly.
 */
const FIELD_LABEL_KEYS: Record<string, string> = {
  // Beneficiary (§3.3)
  full_name: "clients.fullName",
  pid: "clients.pid",
  mother_full_name: "clients.motherName",
  marital_status: "clients.maritalStatus",
  spouse_name: "clients.spouseName",
  spouse_date_of_birth: "clients.spouseDateOfBirth",
  spouse_mother_full_name: "clients.spouseMotherName",
  spouse_pid: "clients.spousePid",
  date_of_birth: "clients.dateOfBirth",
  place_of_birth: "clients.placeOfBirth",
  address: "clients.address",
  phone: "clients.phone",
  category: "clients.category",
  // Case
  land_id: "workflow.landId",
  land_address: "workflow.landAddress",
  assigned_lawyer: "processes.assignedLawyer",
  notes: "workflow.lawyerNotes",
  custom_name: "workflow.customName",
  start_date: "workflow.startDate",
  end_date: "workflow.endDate",
  approval_date: "workflow.approvalDate",
  // Users / catalog
  username: "users.username",
  first_name: "users.firstName",
  last_name: "users.lastName",
  email: "users.email",
  role: "users.role",
  password: "users.password",
  code: "categories.code",
  name: "categories.name",
};

/** The translated label for an API field name, or undefined when it has none. */
export function fieldLabel(t: TFunction, field: string): string | undefined {
  const key = FIELD_LABEL_KEYS[field];
  return key ? t(key) : undefined;
}

/** A `label` function ready to hand to `apiErrorMessage`. */
export const labeller = (t: TFunction) => (field: string) => fieldLabel(t, field);
