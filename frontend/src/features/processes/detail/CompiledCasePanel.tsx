import { FileStack } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useAppDispatch } from "@/app/hooks";
import { toast } from "@/lib/toast";
import { DocumentPreview } from "@/features/documents/DocumentPreview";
import { DocumentRow } from "@/features/documents/DocumentRow";
import { useCompileCaseMutation } from "@/features/documents/generationApi";
import type { DocumentMeta } from "@/features/documents/types";
import { baseApi } from "@/services/baseApi";

import { newestFirst } from "@/features/documents/documentOrder";

import { GeneratedDocumentPanel } from "./GeneratedDocumentPanel";

const COMPILED_TYPE = "CompiledCase";

/**
 * The Step-5 leadership export (§10.3): a summary cover sheet followed by every document on the
 * case, merged into one PDF.
 *
 * **Marking the case complete is what produces it (UC-086)** — the office was pressing two
 * buttons to finish one case, and a case closed without the second press had no export at all.
 * So there is no Compile button before completion; `autoStart` fires the job off the press that
 * closed the case, and the button comes back afterwards as **Recompile**, which is how a case
 * amended after closing gets a fresh file. It also appears on a complete case with no export —
 * an older one, or a compile that failed — since otherwise nothing could ever produce one.
 */
export function CompiledCasePanel({
  processId,
  documents,
  canEdit,
  isComplete,
  autoStart,
}: {
  processId: number;
  documents: DocumentMeta[];
  canEdit: boolean;
  isComplete: boolean;
  /** Set by the mark-complete press itself, so opening an old case never compiles anything. */
  autoStart: boolean;
}) {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const [compile, { isLoading }] = useCompileCaseMutation();

  const compiled = newestFirst(documents, (doc) => doc.document_type === COMPILED_TYPE);
  // Nothing to merge but the cover sheet: an export of an empty case has no value.
  const hasAttachments = documents.some((doc) => doc.document_type !== COMPILED_TYPE);

  return (
    <GeneratedDocumentPanel
      icon={FileStack}
      title={t("workflow.compiledSection")}
      hint={t("workflow.compiledHint")}
      canGenerate={canEdit && (isComplete || compiled.length > 0)}
      unlocked={hasAttachments}
      hasResult={compiled.length > 0}
      starting={isLoading}
      autoStart={autoStart}
      onStart={() => compile({ process: processId }).unwrap()}
      // The output is a new Document on the process — refetch the case so it appears.
      onFinished={() => {
        dispatch(baseApi.util.invalidateTags([{ type: "Process", id: processId }]));
        toast.success(t("common.saved"));
      }}
      labels={{
        generate: t("workflow.compile"),
        regenerate: t("workflow.recompile"),
        busy: t("workflow.compiling"),
        started: t("workflow.compileStarted"),
        failed: t("workflow.compileFailed"),
        empty: t("workflow.noCompiledYet"),
        locked: t("workflow.compileLocked"),
      }}
    >
      <div className="space-y-3">
        <div className="space-y-1">
          {compiled.map((doc, i) => (
            // The newest is already previewed below, so it must not offer its own toggle —
            // that opened a second copy of the same PDF under the first (UC-069).
            <DocumentRow key={doc.id} doc={doc} previewable={i !== 0} />
          ))}
        </div>
        {/* Newest shown inline so it can be checked and printed without leaving the case. */}
        {compiled.length > 0 && (
          <DocumentPreview
            source={{ kind: "document", id: compiled[0].id }}
            title={compiled[0].display_filename}
          />
        )}
      </div>
    </GeneratedDocumentPanel>
  );
}
