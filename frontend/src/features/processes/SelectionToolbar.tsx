import { Printer } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useAppSelector } from "@/app/hooks";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toaster";
import { downloadDocument, downloadGenerationJob } from "@/features/documents/download";
import { useGenerateProcessListMutation } from "@/features/documents/generationApi";
import { useGenerationRun } from "@/features/documents/useGenerationRun";
import { apiErrorMessage } from "@/lib/apiError";

// The letter for the rows ticked on the Processes page (§6.8, UC-016). **One** row produces that
// person's own eligibility letter, filed on their case; **two or more** produce the list letter,
// which spans several people and so is filed under none of them and downloads straight to print.
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
    // The two kinds land in different places: a list letter is a job output with its own
    // endpoint, a single letter is a Document on the case. Asking the job endpoint for the
    // latter 404s, because an eligibility job carries no `output_path`.
    const download =
      job.kind === "eligibility" && job.document
        ? downloadDocument(job.document, `letter_${job.document}.pdf`, token)
        : downloadGenerationJob(job.id, token);
    download.then(onClear).catch(() => toast.error(t("workflow.downloadError")));
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
          {busy
            ? t("workflow.generating")
            : t(selected.length === 1 ? "processes.printSingle" : "processes.printList")}
        </Button>
      </div>
    </div>
  );
}
