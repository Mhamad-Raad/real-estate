import { FileStack } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useCompileCaseMutation } from "@/features/documents/generationApi";
import type { DocumentMeta } from "@/features/documents/types";

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
  const [compile, { isLoading }] = useCompileCaseMutation();

  const compiled = newestFirst(documents, (doc) => doc.document_type === COMPILED_TYPE);
  // Nothing to merge but the cover sheet: an export of an empty case has no value.
  const hasAttachments = documents.some((doc) => doc.document_type !== COMPILED_TYPE);

  return (
    <GeneratedDocumentPanel
      processId={processId}
      documents={compiled}
      icon={FileStack}
      title={t("workflow.compiledSection")}
      hint={t("workflow.compiledHint")}
      canGenerate={canGenerate}
      unlocked={hasAttachments}
      starting={isLoading}
      onStart={() => compile({ process: processId }).unwrap()}
      labels={{
        generate: t("workflow.compile"),
        regenerate: t("workflow.recompile"),
        busy: t("workflow.compiling"),
        started: t("workflow.compileStarted"),
        done: t("common.saved"),
        failed: t("workflow.compileFailed"),
        empty: t("workflow.noCompiledYet"),
        locked: t("workflow.compileLocked"),
      }}
    />
  );
}
