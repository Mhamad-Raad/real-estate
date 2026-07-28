import { FileSignature } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { DocumentType } from "@/features/documents/documentTypesApi";
import { useGenerateEligibilityMutation } from "@/features/documents/generationApi";
import type { DocumentMeta } from "@/features/documents/types";

import { newestFirst } from "@/features/documents/documentOrder";

import { GeneratedDocumentPanel } from "./GeneratedDocumentPanel";

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
  const [generate, { isLoading }] = useGenerateEligibilityMutation();

  const codes = new Set(generatedTypes.map((dt) => dt.code));
  const letters = newestFirst(documents, (doc) => codes.has(doc.document_type));

  return (
    <GeneratedDocumentPanel
      processId={processId}
      documents={letters}
      icon={FileSignature}
      title={t("workflow.generatedSection")}
      canGenerate={canGenerate}
      unlocked={stepComplete}
      starting={isLoading}
      onStart={() => generate({ process: processId }).unwrap()}
      labels={{
        generate: t("workflow.generate"),
        regenerate: t("workflow.regenerate"),
        busy: t("workflow.generating"),
        started: t("workflow.generateStarted"),
        done: t("common.saved"),
        failed: t("workflow.generateFailed"),
        empty: t("workflow.noLetterYet"),
        locked: t("workflow.generateLocked"),
      }}
    />
  );
}
