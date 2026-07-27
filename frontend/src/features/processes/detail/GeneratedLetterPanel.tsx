import { FileSignature } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { useAppDispatch } from "@/app/hooks";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toaster";
import { DocumentRow } from "@/features/documents/DocumentRow";
import type { DocumentType } from "@/features/documents/documentTypesApi";
import {
  isSettled,
  useGenerateEligibilityMutation,
  useGetGenerationJobQuery,
} from "@/features/documents/generationApi";
import type { DocumentMeta } from "@/features/documents/types";
import { apiErrorMessage } from "@/lib/apiError";
import { baseApi } from "@/services/baseApi";

// The letter the system produces for Step 1 (§6.6). Generating is a *result* of finishing Step 1,
// never a requirement of it — so the button unlocks once the step has nothing missing.
export function GeneratedLetterPanel({
  processId,
  documents,
  generatedTypes,
  canGenerate,
  stepComplete,
}: {
  processId: number;
  documents: DocumentMeta[];
  generatedTypes: DocumentType[];
  canGenerate: boolean;
  stepComplete: boolean;
}) {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const [generate, { isLoading: starting }] = useGenerateEligibilityMutation();
  const [jobId, setJobId] = useState<number | null>(null);

  // Poll only while a run is in flight; clearing jobId below stops it (§8).
  const { data: job } = useGetGenerationJobQuery(jobId as number, {
    skip: jobId === null,
    pollingInterval: 1500,
  });

  useEffect(() => {
    if (!job || !isSettled(job.status)) return;
    setJobId(null);
    if (job.status === "done") {
      // The letter is a new Document on the process — pull the detail again so it appears.
      dispatch(baseApi.util.invalidateTags([{ type: "Process", id: processId }]));
      toast.success(t("common.saved"));
    } else {
      toast.error(job.error || t("workflow.generateFailed"));
    }
  }, [job, dispatch, processId, t]);

  const codes = new Set(generatedTypes.map((dt) => dt.code));
  const letters = documents.filter((d) => codes.has(d.document_type));
  const busy = starting || jobId !== null;

  const run = async () => {
    try {
      const started = await generate({ process: processId }).unwrap();
      setJobId(started.id);
      toast.success(t("workflow.generateStarted"));
    } catch (err) {
      toast.error(apiErrorMessage(err, t("workflow.generateFailed")));
    }
  };

  return (
    <div className="space-y-2 rounded-md border border-border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-2 text-sm font-medium">
          <FileSignature className="size-4 text-muted-foreground" />
          {t("workflow.generatedSection")}
        </p>
        {canGenerate && (
          <Button
            size="sm"
            onClick={run}
            disabled={busy || !stepComplete}
            title={stepComplete ? undefined : t("workflow.generateLocked")}
          >
            {busy && <Spinner />}
            {busy
              ? t("workflow.generating")
              : letters.length
                ? t("workflow.regenerate")
                : t("workflow.generate")}
          </Button>
        )}
      </div>

      {letters.length ? (
        <div className="space-y-1">
          {letters.map((doc) => (
            <DocumentRow key={doc.id} doc={doc} />
          ))}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">
          {stepComplete ? t("workflow.noLetterYet") : t("workflow.generateLocked")}
        </p>
      )}
    </div>
  );
}