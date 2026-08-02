import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { useAppSelector } from "@/app/hooks";
import { Dialog } from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toaster";
import { fetchTemplatePreviewUrl } from "@/features/documents/download";

import type { DocumentTemplate } from "./types";

// Shows what the letter actually looks like (§6.6, UC-010) — the page used to show a filename and
// a size, which says nothing about the document the office is about to send. The server renders
// the `.docx` to PDF with sample values; the bytes need an auth header, so they arrive as a blob.
export function TemplatePreviewDialog({
  template,
  onClose,
}: {
  template: DocumentTemplate | null;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const token = useAppSelector((s) => s.auth.access);
  const [url, setUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

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
      title={t("templates.previewTitle")}
      description={t("templates.previewHint")}
      className="max-w-4xl"
    >
      <div className="h-[70vh] w-full overflow-hidden rounded-md border border-border bg-muted">
        {loading || !url ? (
          <div className="flex h-full items-center justify-center">
            <Spinner />
          </div>
        ) : (
          <iframe src={url} title={t("templates.previewTitle")} className="size-full" />
        )}
      </div>
    </Dialog>
  );
}
