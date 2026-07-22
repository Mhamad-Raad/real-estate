export type Role = "admin" | "lawyer";
export type Language = "ckb" | "ar" | "en";
export type Theme = "light" | "dark";

export interface User {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  role: Role;
  language: Language;
  theme: Theme;
  is_admin: boolean;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access: string;
  refresh: string;
  user: User;
}
