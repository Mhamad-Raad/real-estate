/** Machine codes come from `GET /template-types/`; never hard-code the list (§6.6, UC-008). */
export interface TemplateTypeOption {
  code: string;
  /** i18n key, so the code stays stable in the DB while labels stay translatable. */
  display_key: string;
}

export interface DocumentTemplate {
  id: number;
  template_type: string;
  name: string;
  original_filename: string;
  size_bytes: number;
  /** A blank form the office prints as supplied, rather than a letter the system fills in (§6.6). */
  is_blank_form: boolean;
  is_active: boolean;
  uploaded_by: number | null;
  version: number;
  created_at: string;
}
