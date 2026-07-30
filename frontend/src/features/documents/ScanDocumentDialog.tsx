import { ArrowDown, ArrowUp, Camera, ImagePlus, ScanLine, X } from "lucide-react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toaster";
import { useCamera } from "@/hooks/useCamera";
import { apiErrorMessage } from "@/lib/apiError";
import { formatNumber } from "@/lib/format";
import { assemblePagesToPdf, isSupportedPageImage, type ScanPage } from "@/lib/pdfAssembly";

import { useUploadDocumentMutation } from "./documentsApi";

// Mirrors the server's MAX_UPLOAD_BYTES default (§12). The server is still the authority — this
// only spares the lawyer a long upload that ends in a 413 after they photographed twenty pages.
const MAX_SCAN_BYTES = 25 * 1024 * 1024;

/** Scan a paper document with the computer's camera and file it as one PDF (§6.1).
 *
 * Any government paper, not just an ID card: each page is photographed, the pages are assembled
 * in the browser, and the result goes to the ordinary `POST /documents/` upload — the same
 * endpoint, and the same document row, that importing a ready-made PDF produces.
 */
export function ScanDocumentDialog({
  process,
  step,
  documentType,
  instituteEntry = null,
  disabled = false,
}: {
  process: number;
  step: number;
  documentType: string;
  instituteEntry?: number | null;
  disabled?: boolean;
}) {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const [pages, setPages] = useState<ScanPage[]>([]);
  const [busy, setBusy] = useState(false);
  const camera = useCamera();
  const inputRef = useRef<HTMLInputElement>(null);
  const nextId = useRef(0);
  const [upload] = useUploadDocumentMutation();

  const makePage = (file: File): ScanPage => ({
    id: `page-${nextId.current++}`,
    file,
    url: URL.createObjectURL(file),
  });

  const close = () => {
    // Every thumbnail holds an object URL; dropping the state without revoking them leaks the
    // whole scan into memory for as long as the tab lives.
    pages.forEach((page) => URL.revokeObjectURL(page.url));
    setPages([]);
    camera.stop();
    setOpen(false);
  };

  const openCamera = async () => {
    if (!(await camera.open())) toast.error(t("scan.cameraDenied"));
  };

  // The camera stays open after each shot — a multi-page document is photographed page by page.
  const shoot = async () => {
    const file = await camera.capture(`page-${pages.length + 1}.jpg`);
    if (file) setPages((current) => [...current, makePage(file)]);
  };

  const addFiles = async (chosen: FileList) => {
    const accepted: ScanPage[] = [];
    let rejected = 0;
    for (const file of Array.from(chosen)) {
      if (await isSupportedPageImage(file)) accepted.push(makePage(file));
      else rejected += 1;
    }
    if (rejected > 0) toast.error(t("scan.unsupportedFile"));
    if (accepted.length > 0) setPages((current) => [...current, ...accepted]);
  };

  const removePage = (id: string) => {
    // Revoked outside the updater: React may call an updater twice, and side effects do not
    // belong in one.
    const dropped = pages.find((page) => page.id === id);
    if (dropped) URL.revokeObjectURL(dropped.url);
    setPages((current) => current.filter((page) => page.id !== id));
  };

  // Up/down rather than left/right: vertical movement means the same thing in RTL and LTR.
  const movePage = (index: number, delta: number) => {
    setPages((current) => {
      const target = index + delta;
      if (target < 0 || target >= current.length) return current;
      const next = [...current];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  };

  const save = async () => {
    if (pages.length === 0) return;
    setBusy(true);
    try {
      const pdf = await assemblePagesToPdf(
        pages.map((page) => page.file),
        `${documentType}-scan.pdf`,
      );
      if (pdf.size > MAX_SCAN_BYTES) {
        toast.error(t("scan.tooLarge"));
        return;
      }
      await upload({
        process,
        step_number: step,
        document_type: documentType,
        institute_entry: instituteEntry,
        file: pdf,
        input_source: "scanned",
      }).unwrap();
      toast.success(t("workflow.uploaded"));
      close();
    } catch (err) {
      toast.error(apiErrorMessage(err, t("workflow.uploadError")));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={disabled}
        onClick={() => setOpen(true)}
      >
        <ScanLine className="size-4" />
        {t("scan.action")}
      </Button>

      <Dialog
        open={open}
        onClose={() => {
          if (!busy) close();
        }}
        title={t("scan.title")}
        description={t("scan.hint")}
        className="max-w-3xl"
      >
        <div className="space-y-4">
          <div className="flex min-h-48 items-center justify-center overflow-hidden rounded-md border border-dashed border-border bg-muted/40">
            {camera.active ? (
              <video
                ref={camera.videoRef}
                autoPlay
                playsInline
                muted
                className="max-h-64 w-full object-contain"
              />
            ) : (
              <p className="p-6 text-center text-xs text-muted-foreground">
                {pages.length === 0 ? t("scan.noPages") : t("scan.cameraClosed")}
              </p>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            {camera.active ? (
              <>
                <Button type="button" size="sm" disabled={busy} onClick={shoot}>
                  <Camera className="size-4" />
                  {t("scan.shoot")}
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={camera.stop}>
                  <X className="size-4" />
                  {t("scan.closeCamera")}
                </Button>
              </>
            ) : (
              <Button type="button" variant="outline" size="sm" disabled={busy} onClick={openCamera}>
                <Camera className="size-4" />
                {t("scan.useCamera")}
              </Button>
            )}
            <input
              ref={inputRef}
              type="file"
              accept="image/jpeg,image/png"
              multiple
              className="hidden"
              onChange={(event) => {
                if (event.target.files?.length) void addFiles(event.target.files);
                event.target.value = "";
              }}
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={busy}
              onClick={() => inputRef.current?.click()}
            >
              <ImagePlus className="size-4" />
              {t("scan.addFromFile")}
            </Button>
          </div>

          {pages.length > 0 ? (
            <div className="space-y-2">
              <p className="text-sm font-medium">
                {t("scan.pageTally", { pages: formatNumber(pages.length, i18n.language) })}
              </p>
              <ul className="grid max-h-72 grid-cols-2 gap-3 overflow-y-auto sm:grid-cols-4">
                {pages.map((page, index) => (
                  <li key={page.id} className="rounded-md border border-border p-2">
                    <img
                      src={page.url}
                      alt={t("scan.pageAlt", {
                        number: formatNumber(index + 1, i18n.language),
                      })}
                      // Contain, not cover: a cropped thumbnail of an A4 page hides exactly the
                      // header and footer a lawyer uses to tell one page from the next.
                      className="h-28 w-full rounded bg-muted object-contain"
                    />
                    <div className="mt-2 flex items-center justify-between gap-1">
                      <span className="text-xs text-muted-foreground">
                        {formatNumber(index + 1, i18n.language)}
                      </span>
                      <div className="flex gap-1">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          disabled={busy || index === 0}
                          aria-label={t("scan.moveUp")}
                          onClick={() => movePage(index, -1)}
                        >
                          <ArrowUp className="size-4" />
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          disabled={busy || index === pages.length - 1}
                          aria-label={t("scan.moveDown")}
                          onClick={() => movePage(index, 1)}
                        >
                          <ArrowDown className="size-4" />
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          disabled={busy}
                          aria-label={t("scan.removePage")}
                          onClick={() => removePage(page.id)}
                        >
                          <X className="size-4" />
                        </Button>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" disabled={busy} onClick={close}>
              {t("common.cancel")}
            </Button>
            <Button type="button" disabled={busy || pages.length === 0} onClick={save}>
              {busy ? <Spinner /> : null}
              {t("scan.save")}
            </Button>
          </div>
        </div>
      </Dialog>
    </>
  );
}
