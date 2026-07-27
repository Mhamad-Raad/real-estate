import { Printer } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useAppSelector } from "@/app/hooks";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toaster";
import { downloadGenerationJob } from "@/features/documents/download";
import { useGenerateProcessListMutation } from "@/features/documents/generationApi";
import { useGenerationRun } from "@/features/documents/useGenerationRun";
import { apiErrorMessage } from "@/lib/apiError";

// Bulk letter for the rows ticked on the Processes page (§6.8). The output spans several people,
// so it is not filed under any one of them — it downloads straight to the user to print.
export function SelectionToolbar({
  selected,
  onClear,
}: {
  selected: number[];
  onClear: () => void;
}) {
  const { t } = useTranslation();
  const token = useAppSelector((s) => s.auth.access);
  const [generate, { isLoading: starting }] = useGenerateProcessListMutation();
  const { start, busy: running } = useGenerationRun((job) => {
    downloadGenerationJob(job.id, token)
      .then(onClear)
      .catch(() => toast.error(t("workflow.downloadError")));
  });

  if (!selected.length) return null;

  const busy = starting || running;

  const run = async () => {
    try {
      const started = await generate({ process_ids: selected }).unwrap();
      start(started.id);
      toast.success(t("workflow.generateStarted"));
    } catch (err) {
      toast.error(apiErrorMessage(err, t("workflow.generateFailed")));
    }
  };

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-muted/40 px-3 py-2">
      <span className="text-sm">{t("processes.selectedCount", { count: selected.length })}</span>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={onClear} disabled={busy}>
          {t("common.cancel")}
        </Button>
        <Button size="sm" onClick={run} disabled={busy}>
          {busy ? <Spinner /> : <Printer className="size-4" />}
          {busy ? t("workflow.generating") : t("processes.printStep1")}
        </Button>
      </div>
    </div>
  );
}
