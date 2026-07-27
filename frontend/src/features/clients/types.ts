export type MaritalStatus = "single" | "married" | "divorced" | "widowed";

export interface Client {
  id: number;
  full_name: string;
  pid: string;
  mother_full_name: string;
  marital_status: MaritalStatus;
  spouse_name: string;
  spouse_date_of_birth: string | null;
  spouse_mother_full_name: string;
  is_married: boolean;
  date_of_birth: string | null;
  place_of_birth: string;
  address: string;
  phone: string;
  category: number | null;
  created_by: number | null;
  version: number;
  created_at: string;
}

export interface ClientInput {
  full_name: string;
  pid: string;
  mother_full_name: string;
  marital_status: MaritalStatus;
  spouse_name: string;
  spouse_date_of_birth: string | null;
  spouse_mother_full_name: string;
  date_of_birth: string | null;
  place_of_birth: string;
  address: string;
  phone: string;
  category: number | null;
}

export interface DuplicateCheckResult {
  pid_matches: Client[];
  mother_name_matches: Client[];
}
