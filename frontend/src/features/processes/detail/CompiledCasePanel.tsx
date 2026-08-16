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
  const [compile, { isLoading }] = useCompileCaseMutation();

  const compiled = newestFirst(documents, (doc) => doc.document_type === COMPILED_TYPE);
  // Nothing to merge but the cover sheet: an export of an empty case has no value.
  const hasAttachments = documents.some((doc) => doc.document_type !== COMPILED_TYPE);

  return (
    <GeneratedDocumentPanel
      icon={FileStack}
      title={t("workflow.compiledSection")}
      hint={t("workflow.compiledHint")}
      canGenerate={canGenerate}
      unlocked={hasAttachments}
      hasResult={compiled.length > 0}
      starting={isLoading}
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
