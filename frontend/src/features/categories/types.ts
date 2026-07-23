export interface Category {
  id: number;
  code: string;
  name: string;
  version: number;
}

export type CategoryInput = Pick<Category, "code" | "name">;
