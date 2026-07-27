// Document bytes need the auth header, so a plain <a href> won't do — fetch as a blob and
// trigger a download with the friendly filename the server provides.
export async function downloadDocument(id: number, filename: string, token: string | null) {
  const res = await fetch(`/api/v1/documents/${id}/file/`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error("download failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** Same auth-checked fetch for a generated list letter, which is a job output, not a Document. */
export async function downloadGenerationJob(id: number, token: string | null) {
  const res = await fetch(`/api/v1/generation-jobs/${id}/file/`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error("download failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `list_${id}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
