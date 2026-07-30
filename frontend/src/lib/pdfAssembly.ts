/** Browser-side scan assembly — camera pages into one PDF, entirely offline (§6.1).
 *
 * The assembly happens here rather than on the server for one contract reason: `POST /documents/`
 * takes a single `file`, so building the PDF in the browser keeps the camera a UI addition
 * instead of a new multi-file endpoint. It also lets the lawyer see, reorder and retake pages
 * before anything is uploaded, which is the whole point of scanning paper you are holding.
 */

// A4 in PDF points (72 per inch), used in whichever orientation each page was shot in.
const A4_SHORT = 595.28;
const A4_LONG = 841.89;

type PageImageKind = "jpeg" | "png";

// The only two formats pdf-lib can embed; anything else is refused at the point a page is added.
const MAGIC: Record<PageImageKind, number[]> = {
  jpeg: [0xff, 0xd8, 0xff],
  png: [0x89, 0x50, 0x4e, 0x47],
};

function detect(head: Uint8Array): PageImageKind | null {
  for (const [kind, magic] of Object.entries(MAGIC)) {
    if (magic.every((byte, i) => head[i] === byte)) return kind as PageImageKind;
  }
  return null;
}

/** Whether a picked file is a page image we can embed — decided on magic bytes, not on the
 * browser's guess at a type, which is derived from the extension and can simply be wrong. */
export async function isSupportedPageImage(file: File): Promise<boolean> {
  const head = new Uint8Array(await file.slice(0, 8).arrayBuffer());
  return detect(head) !== null;
}

/** Assemble captured page images into a single multi-page PDF.
 *
 * The original image bytes are embedded untouched — only the page box around them is set — so
 * nothing is resampled and a later OCR read still sees the full capture resolution.
 */
export async function assemblePagesToPdf(pages: File[], filename: string): Promise<File> {
  if (pages.length === 0) throw new Error("Cannot assemble a PDF with no pages.");

  // Loaded on demand: pdf-lib is ~470 kB and only a lawyer who actually scans ever needs it.
  // It is still bundled into `dist` (never a CDN), so the chunk is served by the office's own
  // Nginx and the offline guarantee is untouched.
  const { PDFDocument } = await import("pdf-lib");
  const pdf = await PDFDocument.create();
  for (const page of pages) {
    const bytes = new Uint8Array(await page.arrayBuffer());
    const kind = detect(bytes);
    if (!kind) throw new Error(`Unsupported page image: ${page.name}`);
    const image = kind === "jpeg" ? await pdf.embedJpg(bytes) : await pdf.embedPng(bytes);

    // A4 in the shot's own orientation, so a landscape page is not letterboxed into portrait.
    const landscape = image.width > image.height;
    const width = landscape ? A4_LONG : A4_SHORT;
    const height = landscape ? A4_SHORT : A4_LONG;
    // Uniform page sizes matter downstream: the compiled case file (§10.3) merges these pages
    // with generated letters, and mixed page boxes print as a ragged stack.
    const sheet = pdf.addPage([width, height]);
    const fitted = image.scaleToFit(width, height);
    sheet.drawImage(image, {
      x: (width - fitted.width) / 2,
      y: (height - fitted.height) / 2,
      width: fitted.width,
      height: fitted.height,
    });
  }

  // `File` copies exactly the view's bytes, so the saved array goes straight in — no intermediate
  // copy of a scan that may be tens of megabytes. The cast only narrows away `SharedArrayBuffer`,
  // which `BlobPart` excludes and `save()` never returns.
  const saved = (await pdf.save()) as Uint8Array<ArrayBuffer>;
  return new File([saved], filename, { type: "application/pdf" });
}
