import { describe, expect, it, vi, beforeEach } from "vitest";

import { downloadGenerationJob } from "./download";

// The office raised the download name once already (UC-058): a compiled case arrived as a blob id.
// A code list arriving as `list_29.pdf` is the same complaint with a different file.
describe("downloadGenerationJob naming", () => {
  const clicked: string[] = [];

  beforeEach(() => {
    clicked.length = 0;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, blob: async () => new Blob(["x"]) }));
    vi.stubGlobal("URL", { createObjectURL: () => "blob:x", revokeObjectURL: () => {} });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      clicked.push(this.download);
    });
  });

  it("names a code list after the code list, not the letter", async () => {
    await downloadGenerationJob(29, "t", "process_codes");
    expect(clicked).toEqual(["codes_29.pdf"]);
  });

  it("still names the list letter as before", async () => {
    await downloadGenerationJob(7, "t", "process_list");
    expect(clicked).toEqual(["list_7.pdf"]);
  });

  it("falls back to a neutral name for a kind it does not know", async () => {
    await downloadGenerationJob(3, "t", "something_new");
    expect(clicked).toEqual(["document_3.pdf"]);
  });
});
