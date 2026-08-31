import { FileStack } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { DocumentPreview } from "@/features/documents/DocumentPreview";
import { DocumentRow } from "@/features/documents/DocumentRow";
import { useCompileCaseMutation } from "@/features/documents/generationApi";
import type { DocumentMeta } from "@/features/documents/types";

import { newestFirst } from "@/features/documents/documentOrder";

import { GeneratedDocumentPanel } from "./GeneratedDocumentPanel";

const COMPILED_TYPE = "CompiledCase";

// An export the app itself stored, before UC-118 — never a scan the office carried in.
const isStoredExport = (doc: DocumentMeta) =>
  doc.document_type === COMPILED_TYPE && doc.input_source === "system_generated";

/**
 * The Step-5 leadership export (§10.3): a summary cover sheet followed by every document on the
 * case, merged into one PDF.
 *
 * **Marking the case complete is what produces it (UC-086)** — the office was pressing two
 * buttons to finish one case, and a case closed without the second press had no export at all.
 * So there is no Compile button before completion; `autoStart` fires the job off the press that
 * closed the case, and the button stays afterwards as **Recompile**.
 *
 * **It is not kept on the case (UC-118).** The export is every paper on the case merged again, so
 * storing it doubled what a closed case cost on disk. Like the Step-1 letter it is a one-read job
 * file: previewed and printed here, gone once the case is reloaded, one click to produce again.
 * What the case *does* still carry is a scanned case file from the backlog door (UC-114) or an
 * export stored before this rule — those are listed, since they are real documents on the case.
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
  const [compile, { isLoading }] = useCompileCaseMutation();
  const [jobId, setJobId] = useState<number | null>(null);

  const filed = newestFirst(documents, (doc) => doc.document_type === COMPILED_TYPE);
  // Nothing to merge but the cover sheet: an export of an empty case has no value. A scanned case
  // file counts — it *is* the case's papers — while a stored export would only nest inside itself.
  const hasAttachments = documents.some((doc) => !isStoredExport(doc));
  // The fresh export is previewed inline while it lasts; otherwise the newest filed one is.
  const inline = jobId === null && filed.length > 0 ? filed[0] : null;

  return (
    <GeneratedDocumentPanel
      icon={FileStack}
      title={t("workflow.compiledSection")}
      hint={t("workflow.compiledHint")}
      canGenerate={canEdit && isComplete}
      unlocked={hasAttachments}
      hasResult={jobId !== null || filed.length > 0}
      starting={isLoading}
      autoStart={autoStart}
      onStart={() => compile({ process: processId }).unwrap()}
      onFinished={(job) => setJobId(job.id)}
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
          {filed.map((doc) => (
            // The one already previewed below must not offer its own toggle — that opened a
            // second copy of the same PDF under the first (UC-069).
            <DocumentRow key={doc.id} doc={doc} previewable={doc !== inline} />
          ))}
        </div>
        {jobId !== null && (
          // The download name comes from the server's `Content-Disposition` (§6.7); this title is
          // only the iframe's label and the fallback.
          <DocumentPreview source={{ kind: "job", id: jobId }} title={t("workflow.compiledSection")} />
        )}
        {inline && (
          <DocumentPreview source={{ kind: "document", id: inline.id }} title={inline.display_filename} />
        )}
      </div>
    </GeneratedDocumentPanel>
  );
}
