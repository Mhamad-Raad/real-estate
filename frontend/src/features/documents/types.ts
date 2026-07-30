export interface DocumentMeta {
  id: number;
  process: number;
  step_number: number;
  document_type: string;
  institute_entry: number | null;
  input_source: string;
  ocr_status: string;
  verification_status: string;
  display_filename: string;
  size_bytes: number;
  uploaded_by: number;
  created_at: string;
  version: number;
}

export interface UploadArgs {
  process: number;
  step_number: number;
  document_type: string;
  institute_entry?: number | null;
  file: File;
  // How the paper got here (§4.4). Omitted means imported — the server's own default.
  input_source?: "imported" | "scanned";
}
