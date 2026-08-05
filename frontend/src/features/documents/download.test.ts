import { describe, expect, it, vi, beforeEach } from "vitest";

import { downloadFile, downloadGenerationJob } from "./download";

// The office raised the download name twice (UC-058, UC-066). It is settled the same way as the
// stored path: **the server names the file**, and the client stops inventing one. These pin that
// contract, because the previous fix put a stem table on the client and it drifted immediately.
describe("download naming", () => {
  const clicked: string[] = [];

  const respondWith = (headers?: Record<string, string>) =>
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        blob: async () => new Blob(["x"]),
        headers: headers
          ? { get: (k: string) => headers[k.toLowerCase()] ?? null }
          : undefined,
      }),
    );

  beforeEach(() => {
    clicked.length = 0;
    vi.stubGlobal("URL", { createObjectURL: () => "blob:x", revokeObjectURL: () => {} });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      clicked.push(this.download);
    });
  });

  it("saves a generated file under the Sorani name the server sent", async () => {
    // RFC 5987 is the form a non-ASCII name arrives in, and every generated name is Sorani (§6.7).
    respondWith({
      "content-disposition":
        "attachment; filename*=utf-8''%D9%84%DB%8C%D8%B3%D8%AA%DB%8C%20%DA%A9%DB%86%D8%AF%DB%95%DA%A9%D8%A7%D9%86_29.pdf",
    });

    await downloadGenerationJob(29, "t");

    expect(clicked).toEqual(["لیستی کۆدەکان_29.pdf"]);
  });

  it("reads the plain filename form too", async () => {
    respondWith({ "content-disposition": 'attachment; filename="A18_case.pdf"' });

    await downloadFile("/x", "fallback.pdf", "t");

    expect(clicked).toEqual(["A18_case.pdf"]);
  });

  it("keeps the caller's name when the server sends no header", async () => {
    respondWith();

    await downloadGenerationJob(3, "t");

    expect(clicked).toEqual(["document_3.pdf"]);
  });

  it("keeps the caller's name rather than throwing on a malformed header", async () => {
    respondWith({ "content-disposition": "attachment; filename*=utf-8''%E0%A4%A" });

    await downloadFile("/x", "fallback.pdf", "t");

    expect(clicked).toEqual(["fallback.pdf"]);
  });
});
