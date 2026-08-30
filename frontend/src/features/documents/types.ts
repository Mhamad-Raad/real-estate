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
  /** Pages in the stored PDF — both sides of a card live in one document (UC-083). */
  page_count: number;
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

// Mirrors the server's MAX_UPLOAD_BYTES default (§12). The server stays the authority — this only
// spares the lawyer a long upload that ends in a 413 after they photographed twenty pages.
export const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;
