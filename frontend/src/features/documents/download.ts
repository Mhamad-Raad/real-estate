/** The name the server put in `Content-Disposition`, if it sent one.
 *
 * Non-ASCII names travel RFC 5987-encoded (`filename*=utf-8''…`) — every generated name is Sorani
 * (§6.7), so that is the branch that matters; the plain `filename=` form is read as a fallback.
 */
function serverFilename(res: Response): string | undefined {
  // Optional-chained: a stubbed or opaque response may carry no `headers` at all, and a missing
  // server name simply means the caller's fallback stands.
  const header = res.headers?.get?.("content-disposition");
  if (!header) return undefined;
  const encoded = /filename\*=(?:utf-8|UTF-8)''([^;]+)/.exec(header);
  if (encoded) {
    try {
      return decodeURIComponent(encoded[1].trim());
    } catch {
      return undefined; // malformed percent-encoding: fall back to the caller's name
    }
  }
  return /filename="?([^";]+)"?/.exec(header)?.[1]?.trim() || undefined;
}

// Every protected file needs the auth header, so a plain <a href> won't do — fetch as a blob
// and trigger a download from an object URL.
//
// `filename` is only a **fallback**. The server names every file it stores or generates (§6.7),
// so what it sends wins — otherwise each caller invents its own name and they drift, which is how
// a compiled case came to be saved as `case_41.pdf` instead of the name the office reads (UC-066).
export async function downloadFile(url: string, filename: string, token: string | null) {
  const res = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!res.ok) throw new Error("download failed");
  filename = serverFilename(res) ?? filename;
  const objectUrl = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(objectUrl);
}

/**
 * Where a PDF the app can show comes from. Two shapes, because not everything the office reads is
 * filed on a case: the Step-1 letter is a job output (UC-075), yet it is previewed, printed and
 * downloaded through exactly the same controls as a filed document.
 */
export type FileSource = { kind: "document"; id: number } | { kind: "job"; id: number };

export const fileUrlFor = (source: FileSource) =>
  source.kind === "document"
    ? `/api/v1/documents/${source.id}/file/`
    : `/api/v1/generation-jobs/${source.id}/file/`;

/** Uses the friendly filename the server composed for the document. */
export async function downloadDocument(id: number, filename: string, token: string | null) {
  return downloadFile(`/api/v1/documents/${id}/file/`, filename, token);
}

/** A generated list is a job output, not a Document, so it has its own endpoint.
 *
 * No stem table here any more: the server names each kind (UC-066). The fallback only applies if
 * it ever stops sending a `Content-Disposition`.
 */
export async function downloadGenerationJob(id: number, token: string | null) {
  return downloadFile(`/api/v1/generation-jobs/${id}/file/`, `document_${id}.pdf`, token);
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

const templatePreviewUrl = (id: number) => `/api/v1/document-templates/${id}/preview/`;

/** A letter is a `.docx` the server renders to PDF with sample data; a blank form is served as
 * the stored PDF itself (§6.6). Both arrive here as PDF bytes. */
export async function fetchTemplatePreviewUrl(id: number, token: string | null) {
  return fetchBlobUrl(templatePreviewUrl(id), token);
}

/** Saves what the dialog is showing. The blank form is the one the office keeps a paper copy of,
 * so it must land under the Sorani name the server sends, not the blob id (UC-058). */
export async function downloadTemplatePreview(id: number, filename: string, token: string | null) {
  return downloadFile(templatePreviewUrl(id), filename, token);
}
