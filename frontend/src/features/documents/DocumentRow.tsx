import { Download, Eye, FileText, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useAppSelector } from "@/app/hooks";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/toaster";
import { apiErrorMessage } from "@/lib/apiError";

import { DocumentPreview } from "./DocumentPreview";
import { useDeleteDocumentMutation } from "./documentsApi";
import { downloadDocument } from "./download";
import type { DocumentMeta } from "./types";

// One stored document: click the name to download (auth-checked stream), open it in place, or
// soft-delete it. The preview is the same component the generated letters use — it was wired
// only to those, so nothing a lawyer *uploaded* could be looked at without downloading (UC-042).
export function DocumentRow({ doc }: { doc: DocumentMeta }) {
  const { t } = useTranslation();
  const token = useAppSelector((s) => s.auth.access);
  const [remove, { isLoading }] = useDeleteDocumentMutation();
  // Closed by default, and mounted only while open — a step can hold a dozen papers, and each
  // preview fetches the whole file.
  const [open, setOpen] = useState(false);

  const download = async () => {
    try {
      await downloadDocument(doc.id, doc.display_filename, token);
    } catch {
      toast.error(t("workflow.downloadError"));
    }
  };

  const del = async () => {
    try {
      await remove({ id: doc.id, process: doc.process }).unwrap();
      toast.success(t("common.deleted"));
    } catch (err) {
      toast.error(apiErrorMessage(err, t("common.deleteError")));
    }
  };

  return (
    <div className="rounded-md bg-muted/50 text-sm">
      <div className="flex items-center justify-between gap-2 px-3 py-2">
      <button
        type="button"
        onClick={download}
        className="flex min-w-0 items-center gap-2 text-start hover:underline"
        title={t("workflow.download")}
      >
        <FileText className="size-4 shrink-0 text-muted-foreground" />
        <span className="truncate">{doc.display_filename}</span>
        <Download className="size-3.5 shrink-0 text-muted-foreground" />
      </button>
      <div className="flex shrink-0 items-center gap-1">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-7"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-label={t("workflow.preview")}
        >
          <Eye className="size-4" />
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-7 text-destructive"
          onClick={del}
          disabled={isLoading}
          aria-label={t("common.delete")}
        >
          <Trash2 className="size-4" />
        </Button>
      </div>
      </div>
      {open && (
        <div className="border-t border-border px-3 py-3">
          <DocumentPreview documentId={doc.id} title={doc.display_filename} />
        </div>
      )}
    </div>
  );
}
