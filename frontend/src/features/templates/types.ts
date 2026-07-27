export type TemplateType = "eligibility_single" | "process_list";

export interface DocumentTemplate {
  id: number;
  template_type: TemplateType;
  name: string;
  original_filename: string;
  size_bytes: number;
  is_active: boolean;
  uploaded_by: number | null;
  version: number;
  created_at: string;
}
