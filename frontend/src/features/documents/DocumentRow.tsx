import { Download, FileText, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useAppSelector } from "@/app/hooks";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/toaster";
import { apiErrorMessage } from "@/lib/apiError";

import { useDeleteDocumentMutation } from "./documentsApi";
import { downloadDocument } from "./download";
import type { DocumentMeta } from "./types";

// One stored document: click the name to download (auth-checked stream), or soft-delete it.
export function DocumentRow({ doc }: { doc: DocumentMeta }) {
  const { t } = useTranslation();
  const token = useAppSelector((s) => s.auth.access);
  const [remove, { isLoading }] = useDeleteDocumentMutation();

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
    <div className="flex items-center justify-between gap-2 rounded-md bg-muted/50 px-3 py-2 text-sm">
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
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="size-7 shrink-0 text-destructive"
        onClick={del}
        disabled={isLoading}
        aria-label={t("common.delete")}
      >
        <Trash2 className="size-4" />
      </Button>
    </div>
  );
}
