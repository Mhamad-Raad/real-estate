import { Download, Printer } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { useAppSelector } from "@/app/hooks";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/lib/toast";
import { downloadTemplatePreview, fetchTemplatePreviewUrl } from "@/features/documents/download";

import type { DocumentTemplate } from "./types";

// Shows what the letter actually looks like (§6.6, UC-010) — the page used to show a filename and
// a size, which says nothing about the document the office is about to send. The server renders
// the `.docx` to PDF with sample values; the bytes need an auth header, so they arrive as a blob.
//
// `blankForm` switches this from "here is the letter" to a working tool: the request form is
// printed FROM here, signed, and scanned back in on Step 1 (UC-039), so Print and Download are the
// point of the dialog rather than a convenience.
//
// They are deliberately NOT offered for a letter. A letter preview is filled with sample values,
// and this module exists because "a preview must never be mistaken for a real beneficiary's
// letter" — putting a Download and a Print on it hands the office a way to put one on paper.
export function TemplatePreviewDialog({
  template,
  blankForm = false,
  onClose,
}: {
  template: DocumentTemplate | null;
  blankForm?: boolean;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const token = useAppSelector((s) => s.auth.access);
  const [url, setUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const frame = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    if (!template) {
      setUrl(null);
      return;
    }
    let objectUrl: string | null = null;
    let cancelled = false;
    setLoading(true);

    fetchTemplatePreviewUrl(template.id, token)
      .then((created) => {
        // Rendering takes a second or two, so the dialog may already have moved on.
        if (cancelled) {
          URL.revokeObjectURL(created);
          return;
        }
        objectUrl = created;
        setUrl(created);
      })
      .catch(() => toast.error(t("workflow.previewError")))
      .finally(() => !cancelled && setLoading(false));

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [template, token, t]);

  return (
    <Dialog
      open={Boolean(template)}
      onClose={onClose}
      title={t(blankForm ? "templates.previewTitleForm" : "templates.previewTitle")}
      description={t(blankForm ? "templates.previewHintForm" : "templates.previewHint")}
      className="max-w-4xl"
    >
      <div className="space-y-2">
        {blankForm && (
          <div className="flex items-center justify-end gap-2">
            {/* Without these the only controls are the PDF viewer's own, inside the iframe — and
                its download names the file after the blob URL, not the name the office reads on
                paper (UC-058). */}
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={!url || !template}
              onClick={() =>
                template &&
                downloadTemplatePreview(template.id, `${template.name}.pdf`, token).catch(() =>
                  toast.error(t("workflow.downloadError")),
                )
              }
            >
              <Download className="size-4" />
              {t("common.download")}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={!url}
              onClick={() => frame.current?.contentWindow?.print()}
            >
              <Printer className="size-4" />
              {t("workflow.print")}
            </Button>
          </div>
        )}

        <div className="h-[70vh] w-full overflow-hidden rounded-md border border-border bg-muted">
          {loading || !url ? (
            <div className="flex h-full items-center justify-center">
              <Spinner />
            </div>
          ) : (
            <iframe
              ref={frame}
              src={url}
              title={t(blankForm ? "templates.previewTitleForm" : "templates.previewTitle")}
              className="size-full"
            />
          )}
        </div>
      </div>
    </Dialog>
  );
}
