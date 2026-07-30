import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PDFDocument } from "pdf-lib";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { jpegLandscape, jpegPortrait } from "@/test/images";

import { MAX_SCAN_BYTES, ScanDocumentDialog } from "./ScanDocumentDialog";
import type { UploadArgs } from "./types";

// Only the assembled size is faked — the real assembler still runs, so the guard is tested
// against a genuine PDF rather than against a stub that could drift from it.
const oversize = vi.hoisted(() => ({ next: false }));
vi.mock("@/lib/pdfAssembly", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/pdfAssembly")>();
  return {
    ...actual,
    assemblePagesToPdf: async (pages: File[], name: string) => {
      const pdf = await actual.assemblePagesToPdf(pages, name);
      if (oversize.next) Object.defineProperty(pdf, "size", { value: MAX_SCAN_BYTES + 1 });
      return pdf;
    },
  };
});

const unwrap = vi.fn().mockResolvedValue({ id: 3 });
const uploadMutation = vi.fn((_args: UploadArgs) => ({ unwrap }));

/** What the component actually asked the upload endpoint to store. */
const uploaded = () => uploadMutation.mock.calls[0][0];
const toastError = vi.fn();
const toastSuccess = vi.fn();

vi.mock("@/components/ui/toaster", () => ({
  toast: {
    success: (...args: unknown[]) => toastSuccess(...args),
    error: (...args: unknown[]) => toastError(...args),
    info: vi.fn(),
  },
}));
vi.mock("./documentsApi", () => ({
  useUploadDocumentMutation: () => [uploadMutation, { isLoading: false }],
}));

beforeEach(() => {
  oversize.next = false;
  vi.stubGlobal("URL", { ...URL, createObjectURL: () => "blob:x", revokeObjectURL: () => {} });
  uploadMutation.mockClear();
  unwrap.mockClear();
  toastError.mockClear();
  toastSuccess.mockClear();
});

function renderDialog() {
  return render(<ScanDocumentDialog process={4} step={2} documentType="InstituteDoc" />);
}

async function open(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "Scan" }));
}

const pageInput = () => document.querySelector('input[type="file"]') as HTMLInputElement;
const saveButton = () => screen.getByRole("button", { name: "Save as PDF" });

describe("ScanDocumentDialog", () => {
  it("cannot save until at least one page has been captured", async () => {
    const user = userEvent.setup();
    renderDialog();
    await open(user);

    expect(screen.getByText(/No pages yet/)).toBeInTheDocument();
    expect(saveButton()).toBeDisabled();
  });

  it("uploads the captured pages as one scanned PDF", async () => {
    const user = userEvent.setup();
    renderDialog();
    await open(user);

    await user.upload(pageInput(), [jpegPortrait(), jpegLandscape()]);
    await waitFor(() => expect(screen.getAllByRole("listitem")).toHaveLength(2));
    await user.click(saveButton());

    await waitFor(() => expect(uploadMutation).toHaveBeenCalledTimes(1));
    const sent = uploaded();
    expect(sent).toMatchObject({
      process: 4,
      step_number: 2,
      document_type: "InstituteDoc",
      // The row must record that this came off the camera, not out of someone's folder (§4.4).
      input_source: "scanned",
    });
    expect(sent.file.type).toBe("application/pdf");

    // One upload, one document, both pages inside it — not two loose files.
    const assembled = await PDFDocument.load(await sent.file.arrayBuffer());
    expect(assembled.getPageCount()).toBe(2);
    expect(toastSuccess).toHaveBeenCalled();
  });

  it("keeps the pages when the upload fails, so a scan is never lost to a retry", async () => {
    unwrap.mockRejectedValueOnce({ status: 500 });
    const user = userEvent.setup();
    renderDialog();
    await open(user);

    await user.upload(pageInput(), [jpegPortrait()]);
    await waitFor(() => expect(screen.getAllByRole("listitem")).toHaveLength(1));
    await user.click(saveButton());

    await waitFor(() => expect(toastError).toHaveBeenCalled());
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    expect(saveButton()).toBeEnabled();
  });

  it("rejects a file that is not a page image and adds no page for it", async () => {
    const user = userEvent.setup();
    renderDialog();
    await open(user);

    const notAnImage = new File([new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8])], "notes.txt", {
      type: "image/jpeg",
    });
    await user.upload(pageInput(), [notAnImage]);

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("Only JPEG and PNG images can be added as pages."),
    );
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
    expect(saveButton()).toBeDisabled();
  });

  it("reorders pages, and the assembled PDF follows the new order", async () => {
    const user = userEvent.setup();
    renderDialog();
    await open(user);

    // Portrait first, then landscape — then swap them.
    await user.upload(pageInput(), [jpegPortrait(), jpegLandscape()]);
    await waitFor(() => expect(screen.getAllByRole("listitem")).toHaveLength(2));
    await user.click(
      within(screen.getAllByRole("listitem")[1]).getByRole("button", { name: "Move earlier" }),
    );
    await user.click(saveButton());

    await waitFor(() => expect(uploadMutation).toHaveBeenCalledTimes(1));
    const assembled = await PDFDocument.load(await uploaded().file.arrayBuffer());
    // Landscape now leads, which the page boxes prove.
    expect(assembled.getPage(0).getWidth()).toBeGreaterThan(assembled.getPage(0).getHeight());
    expect(assembled.getPage(1).getWidth()).toBeLessThan(assembled.getPage(1).getHeight());
  });

  it("removing a page drops it from the upload", async () => {
    const user = userEvent.setup();
    renderDialog();
    await open(user);

    await user.upload(pageInput(), [jpegPortrait(), jpegLandscape()]);
    await waitFor(() => expect(screen.getAllByRole("listitem")).toHaveLength(2));
    await user.click(
      within(screen.getAllByRole("listitem")[0]).getByRole("button", { name: "Remove page" }),
    );
    expect(screen.getAllByRole("listitem")).toHaveLength(1);

    await user.click(saveButton());
    await waitFor(() => expect(uploadMutation).toHaveBeenCalledTimes(1));
    expect(
      (await PDFDocument.load(await uploaded().file.arrayBuffer())).getPageCount(),
    ).toBe(1);
  });

  it("refuses to upload a scan over the size cap, and keeps the pages so they can be trimmed", async () => {
    oversize.next = true;
    const user = userEvent.setup();
    renderDialog();
    await open(user);

    await user.upload(pageInput(), [jpegPortrait(), jpegLandscape()]);
    await waitFor(() => expect(screen.getAllByRole("listitem")).toHaveLength(2));
    await user.click(saveButton());

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith(
        "The scan is too large. Remove some pages and try again.",
      ),
    );
    // Never sent: the point of the client-side guard is to fail before the long upload, not after.
    expect(uploadMutation).not.toHaveBeenCalled();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(saveButton()).toBeEnabled();
  });

  it("revokes every page's object URL when it unmounts mid-scan", async () => {
    const revoked: string[] = [];
    let n = 0;
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: () => `blob:${n++}`,
      revokeObjectURL: (url: string) => revoked.push(url),
    });
    const user = userEvent.setup();
    const view = renderDialog();
    await open(user);

    await user.upload(pageInput(), [jpegPortrait(), jpegLandscape()]);
    await waitFor(() => expect(screen.getAllByRole("listitem")).toHaveLength(2));

    // Navigating away is not "cancel" — without this the captured pages stay in memory
    // for the life of the tab.
    view.unmount();
    expect(revoked).toEqual(["blob:0", "blob:1"]);
  });

  it("says so when the camera cannot be opened, and still allows adding images", async () => {
    vi.stubGlobal("navigator", {
      ...navigator,
      mediaDevices: { getUserMedia: vi.fn().mockRejectedValue(new Error("denied")) },
    });
    const user = userEvent.setup();
    renderDialog();
    await open(user);

    await user.click(screen.getByRole("button", { name: "Use camera" }));
    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith(
        "Could not open the camera. Add images from a file instead.",
      ),
    );
    expect(screen.getByRole("button", { name: "Add images" })).toBeEnabled();
  });
});
