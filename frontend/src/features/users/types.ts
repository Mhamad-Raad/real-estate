export type Role = "admin" | "lawyer";

export interface AdminUser {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  role: Role;
  is_active: boolean;
  is_admin: boolean;
  version: number;
}

export interface UserCreateInput {
  username: string;
  password: string;
  first_name?: string;
  last_name?: string;
  email?: string;
  role: Role;
}

export interface UserUpdateInput {
  id: number;
  version: number;
  first_name?: string;
  last_name?: string;
  email?: string;
  role?: Role;
  is_active?: boolean;
  password?: string;
}
