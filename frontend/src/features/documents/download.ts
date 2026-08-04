// Every protected file needs the auth header, so a plain <a href> won't do — fetch as a blob
// and trigger a download from an object URL.
export async function downloadFile(url: string, filename: string, token: string | null) {
  const res = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!res.ok) throw new Error("download failed");
  const objectUrl = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(objectUrl);
}

/** Uses the friendly filename the server composed for the document. */
export async function downloadDocument(id: number, filename: string, token: string | null) {
  return downloadFile(`/api/v1/documents/${id}/file/`, filename, token);
}

// Matches the stem the server gives the file on disk, so what the office opens is called what
// the system calls it. Naming a code list `list_29.pdf` is the same complaint they raised about
// the compiled case arriving as a blob id (UC-058).
const JOB_FILE_STEM: Record<string, string> = {
  process_list: "list",
  process_codes: "codes",
  compiled_case: "case",
  eligibility: "letter",
};

/** A generated list is a job output, not a Document, so it has its own endpoint. */
export async function downloadGenerationJob(
  id: number,
  token: string | null,
  kind = "process_list",
) {
  const stem = JOB_FILE_STEM[kind] ?? "document";
  return downloadFile(`/api/v1/generation-jobs/${id}/file/`, `${stem}_${id}.pdf`, token);
}

/** Blob URL for inline preview/print — the file needs the auth header, so it cannot be an <iframe src>. */
export async function fetchBlobUrl(url: string, token: string | null) {
  const res = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error("preview failed");
  return URL.createObjectURL(await res.blob());
}

export async function fetchDocumentBlobUrl(id: number, token: string | null) {
  return fetchBlobUrl(`/api/v1/documents/${id}/file/`, token);
}

/** A template is a `.docx`; the server renders it to PDF with sample data first (§6.6). */
export async function fetchTemplatePreviewUrl(id: number, token: string | null) {
  return fetchBlobUrl(`/api/v1/document-templates/${id}/preview/`, token);
}
