import { PDFDocument } from "pdf-lib";
import { describe, expect, it } from "vitest";

import { jpegLandscape, jpegPortrait, pngPortrait } from "@/test/images";

import { assemblePagesToPdf, isSupportedPageImage } from "./pdfAssembly";

async function pageSizes(pdf: File) {
  const loaded = await PDFDocument.load(await pdf.arrayBuffer());
  return loaded.getPages().map((page) => ({
    width: Math.round(page.getWidth()),
    height: Math.round(page.getHeight()),
  }));
}

describe("isSupportedPageImage", () => {
  it("accepts JPEG and PNG", async () => {
    expect(await isSupportedPageImage(jpegPortrait())).toBe(true);
    expect(await isSupportedPageImage(pngPortrait())).toBe(true);
  });

  it("rejects a file that is not a page image, whatever its type claims", async () => {
    const lying = new File([new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8])], "fake.jpg", {
      type: "image/jpeg",
    });
    expect(await isSupportedPageImage(lying)).toBe(false);
  });

  it("rejects a PDF — importing one is the other upload path, not a scan page", async () => {
    const pdf = new File([new TextEncoder().encode("%PDF-1.4 ...")], "doc.pdf", {
      type: "application/pdf",
    });
    expect(await isSupportedPageImage(pdf)).toBe(false);
  });
});

describe("assemblePagesToPdf", () => {
  it("produces one real PDF page per captured image, in order", async () => {
    const pdf = await assemblePagesToPdf([jpegPortrait(), pngPortrait()], "scan.pdf");

    expect(pdf.name).toBe("scan.pdf");
    expect(pdf.type).toBe("application/pdf");
    const head = new Uint8Array(await pdf.slice(0, 5).arrayBuffer());
    expect(new TextDecoder().decode(head)).toBe("%PDF-");
    expect(await pageSizes(pdf)).toHaveLength(2);
  });

  it("lays each page out on A4 in the orientation it was shot in", async () => {
    const pdf = await assemblePagesToPdf([jpegPortrait(), jpegLandscape()], "scan.pdf");

    // Uniform page boxes keep the compiled case file (§10.3) from printing as a ragged stack.
    expect(await pageSizes(pdf)).toEqual([
      { width: 595, height: 842 },
      { width: 842, height: 595 },
    ]);
  });

  it("refuses to assemble nothing", async () => {
    await expect(assemblePagesToPdf([], "scan.pdf")).rejects.toThrow(/no pages/i);
  });

  it("refuses a page that is not an embeddable image", async () => {
    const junk = new File([new Uint8Array([0, 1, 2, 3, 4, 5, 6, 7])], "junk.jpg");
    await expect(assemblePagesToPdf([junk], "scan.pdf")).rejects.toThrow(/Unsupported page/);
  });
});
