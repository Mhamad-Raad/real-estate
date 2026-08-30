/** The four spouse columns, and which card field each is read from. */
export const SPOUSE_FIELDS = [
  { name: "spouse_name", from: "full_name" },
  { name: "spouse_pid", from: "pid" },
  { name: "spouse_mother_full_name", from: "mother_full_name" },
  { name: "spouse_date_of_birth", from: "date_of_birth" },
] as const;

export type SpouseValues = Record<(typeof SPOUSE_FIELDS)[number]["name"], string>;

export const EMPTY_SPOUSE: SpouseValues = {
  spouse_name: "",
  spouse_pid: "",
  spouse_mother_full_name: "",
  spouse_date_of_birth: "",
};

