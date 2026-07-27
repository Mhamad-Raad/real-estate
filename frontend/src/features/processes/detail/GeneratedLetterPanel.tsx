import { FileSignature } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useAppDispatch } from "@/app/hooks";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toaster";
import { DocumentPreview } from "@/features/documents/DocumentPreview";
import { DocumentRow } from "@/features/documents/DocumentRow";
import type { DocumentType } from "@/features/documents/documentTypesApi";
import { useGenerateEligibilityMutation } from "@/features/documents/generationApi";
import { useGenerationRun } from "@/features/documents/useGenerationRun";
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
  const { start, busy: running } = useGenerationRun(() => {
    // The letter is a new Document on the process — pull the detail again so it appears.
    dispatch(baseApi.util.invalidateTags([{ type: "Process", id: processId }]));
    toast.success(t("common.saved"));
  });

  const codes = new Set(generatedTypes.map((dt) => dt.code));
  const letters = documents.filter((d) => codes.has(d.document_type));
  const busy = starting || running;

  const run = async () => {
    try {
      const started = await generate({ process: processId }).unwrap();
      start(started.id);
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
        <div className="space-y-3">
          <div className="space-y-1">
            {letters.map((doc) => (
              <DocumentRow key={doc.id} doc={doc} />
            ))}
          </div>
          {/* The newest letter is shown inline so it can be checked and printed without leaving
              the case; regenerating swaps it, since the old one is superseded. */}
          <DocumentPreview
            documentId={letters[0].id}
            title={letters[0].display_filename}
          />
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">
          {stepComplete ? t("workflow.noLetterYet") : t("workflow.generateLocked")}
        </p>
      )}
    </div>
  );
}