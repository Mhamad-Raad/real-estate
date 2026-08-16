import { FileSignature } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { DocumentPreview } from "@/features/documents/DocumentPreview";
import { useGenerateEligibilityMutation } from "@/features/documents/generationApi";

import { GeneratedDocumentPanel } from "./GeneratedDocumentPanel";

/**
 * The letter the system produces for Step 1 (§6.6).
 *
 * **It is not filed on the case (UC-075).** The office produces it to read and print; a copy kept
 * on every allocation also ended up merged into the Step-5 compilation, where they do not want
 * it. So the output is a standalone job file — previewed and printed here, and gone from the
 * screen once the case is reloaded, because there is nothing stored to come back to. Generating
 * it again is one click.
 */
export function GeneratedLetterPanel({
  processId,
  canGenerate,
  hasNames,
}: {
  processId: number;
  canGenerate: boolean;
  hasNames: boolean;
}) {
  const { t } = useTranslation();
  const [generate, { isLoading }] = useGenerateEligibilityMutation();
  const [jobId, setJobId] = useState<number | null>(null);

  return (
    <GeneratedDocumentPanel
      icon={FileSignature}
      title={t("workflow.generatedSection")}
      hint={t("workflow.letterNotFiled")}
      canGenerate={canGenerate}
      // Generation was never gated server-side; the button unlocks on the names alone, which is
      // all the letter renders (UC-038).
      unlocked={hasNames}
      hasResult={jobId !== null}
      starting={isLoading}
      onStart={() => generate({ process: processId }).unwrap()}
      onFinished={(job) => setJobId(job.id)}
      labels={{
        generate: t("workflow.generate"),
        regenerate: t("workflow.regenerate"),
        busy: t("workflow.generating"),
        started: t("workflow.generateStarted"),
        failed: t("workflow.generateFailed"),
        empty: t("workflow.noLetterYet"),
        locked: t("workflow.generateLocked"),
      }}
    >
      {jobId !== null && (
        // The download name comes from the server's `Content-Disposition` (§6.7); this title is
        // only the iframe's label and the fallback.
        <DocumentPreview source={{ kind: "job", id: jobId }} title={t("workflow.generatedSection")} />
      )}
    </GeneratedDocumentPanel>
  );
}
