import { FileStack } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useAppDispatch } from "@/app/hooks";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toaster";
import { DocumentPreview } from "@/features/documents/DocumentPreview";
import { DocumentRow } from "@/features/documents/DocumentRow";
import { useCompileCaseMutation } from "@/features/documents/generationApi";
import { useGenerationRun } from "@/features/documents/useGenerationRun";
import type { DocumentMeta } from "@/features/documents/types";
import { apiErrorMessage } from "@/lib/apiError";
import { baseApi } from "@/services/baseApi";

const COMPILED_TYPE = "CompiledCase";

// The Step-5 leadership export (§10.3): a summary cover sheet followed by every document on the
// case, merged into one PDF. Available before completion too — the compiled file is often what
// the reviewer reads *in order to* decide.
export function CompiledCasePanel({
  processId,
  documents,
  canGenerate,
}: {
  processId: number;
  documents: DocumentMeta[];
  canGenerate: boolean;
}) {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const [compile, { isLoading: starting }] = useCompileCaseMutation();
  const { start, busy: running } = useGenerationRun(() => {
    // The export becomes a new Document on the process — refetch so it appears.
    dispatch(baseApi.util.invalidateTags([{ type: "Process", id: processId }]));
    toast.success(t("common.saved"));
  });

  // Superseding leaves exactly one live export, but don't trust the payload's order for it.
  const compiled = documents
    .filter((doc) => doc.document_type === COMPILED_TYPE)
    .slice()
    .sort((a, b) => b.id - a.id);
  // Nothing to merge but the cover sheet: an export of an empty case has no value.
  const hasAttachments = documents.some((doc) => doc.document_type !== COMPILED_TYPE);
  const busy = starting || running;

  const run = async () => {
    try {
      const started = await compile({ process: processId }).unwrap();
      start(started.id);
      toast.success(t("workflow.compileStarted"));
    } catch (err) {
      toast.error(apiErrorMessage(err, t("workflow.compileFailed")));
    }
  };

  return (
    <div className="space-y-2 rounded-md border border-border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-2 text-sm font-medium">
          <FileStack className="size-4 text-muted-foreground" />
          {t("workflow.compiledSection")}
        </p>
        {canGenerate && (
          <Button
            size="sm"
            onClick={run}
            disabled={busy || !hasAttachments}
            title={hasAttachments ? undefined : t("workflow.compileLocked")}
          >
            {busy && <Spinner />}
            {busy
              ? t("workflow.compiling")
              : compiled.length
                ? t("workflow.recompile")
                : t("workflow.compile")}
          </Button>
        )}
      </div>
      <p className="text-xs text-muted-foreground">{t("workflow.compiledHint")}</p>

      {compiled.length ? (
        <div className="space-y-3">
          <div className="space-y-1">
            {compiled.map((doc) => (
              <DocumentRow key={doc.id} doc={doc} />
            ))}
          </div>
          {/* Shown inline so it can be checked and printed without leaving the case. */}
          <DocumentPreview documentId={compiled[0].id} title={compiled[0].display_filename} />
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">
          {hasAttachments ? t("workflow.noCompiledYet") : t("workflow.compileLocked")}
        </p>
      )}
    </div>
  );
}
