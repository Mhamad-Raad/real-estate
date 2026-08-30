import { useTranslation } from "react-i18next";

import { Label } from "@/components/ui/label";
import { DocumentRow } from "@/features/documents/DocumentRow";
import { DocumentUpload } from "@/features/documents/DocumentUpload";
import {
  documentTypeLabel,
  useListDocumentTypesQuery,
  type DocumentPart,
} from "@/features/documents/documentTypesApi";
import { useNum } from "@/hooks/useNum";

import type { ProcessDetail } from "../types";

// Each kind of part brings its own wording: a card has sides, the municipality form and its
// letter have pages, everything else is files (UC-109). Listed rather than built from the noun so
// every key a screen can render is greppable.
const PART_WORDS: Record<DocumentPart, { complete: string; expected: string; full: string }> = {
  file: {
    complete: "workflow.filesComplete",
    expected: "workflow.filesExpected",
    full: "errors.slot.filesFull",
  },
  side: {
    complete: "workflow.sidesComplete",
    expected: "workflow.sidesExpected",
    full: "errors.slot.sidesFull",
  },
  page: {
    complete: "workflow.pagesComplete",
    expected: "workflow.pagesExpected",
    full: "errors.slot.pagesFull",
  },
};

/**
 * The named upload slots a step owns, laid out from the shared vocabulary so a slot can never go
 * missing for something the backend requires (§6.7). Used by Step 1 and — since the real-estate
 * paper moved — Step 4 (UC-037).
 */
export function StepDocumentSlots({
  process,
  step,
  canEdit,
}: {
  process: ProcessDetail;
  step: number;
  canEdit: boolean;
}) {
  const { t } = useTranslation();
  const num = useNum();
  const { data: documentTypes } = useListDocumentTypesQuery();
  const docs = process.documents.filter((d) => d.step_number === step);

  return (
    <>
      {(documentTypes ?? [])
        .filter(
          (dt) =>
            dt.step === step &&
            // Generated letters are output, not something anyone uploads.
            !dt.generated &&
            // A conditional slot still shows while it holds a file: a client who stops being
            // married would otherwise leave an uploaded spouse ID on disk with no way to see
            // or remove it.
            (!dt.only_when_married ||
              process.client_detail.is_married ||
              docs.some((d) => d.document_type === dt.code)),
        )
        .map((documentType) => {
          const { code: type, display_key, expected_parts: expected, part } = documentType;
          const words = PART_WORDS[part];
          const forType = docs.filter((d) => d.document_type === type);
          // A card is ONE document holding both sides, and the municipality form and its letter
          // may arrive as one two-page PDF — both are counted in pages, because counting rows
          // reported either as "1 of 2 files" (UC-083, UC-109).
          const byPage = part !== "file";
          const filed = byPage
            ? forType.reduce((total, d) => total + d.page_count, 0)
            : forType.length;
          // Capped at what the slot asks for: this hint answers "is it complete?", and a card
          // scanned as a three-page PDF read "3 of 2 sides", which looks like a fault rather than
          // an answer (UC-084). Nothing is hidden — every file is still listed underneath.
          const have = Math.min(filed, expected);
          // A full slot takes nothing more (UC-085) — the backend refuses it either way, and a
          // live case can already sit over capacity, so this asks `>=` rather than `===`.
          const full = filed >= expected;
          return (
            <div key={type} className="space-y-2">
              <div className="flex items-center justify-between gap-2">
                <Label>
                  {documentTypeLabel(documentType, t(display_key))}
                  {/* Only where the office files more than one part — it says how many are
                      wanted and how many are in, without blocking the step (UC-055). */}
                  {/* Only while it is still actionable. A finished card said "2 of 2 sides", which
                      is arithmetic the reader has to do to learn nothing — it now says it is
                      complete, and says nothing at all when the slot is empty and the line below
                      already reports that (UC-103). */}
                  {expected > 1 && filed > 0 && (
                    <span className="ms-2 text-xs font-normal text-muted-foreground">
                      {full
                        ? t(words.complete)
                        : t(words.expected, { have: num(have), want: num(expected) })}
                    </span>
                  )}
                </Label>
                {canEdit && (
                  <DocumentUpload
                    process={process.id}
                    step={step}
                    documentType={type}
                    label={t("workflow.import")}
                    // Both parts of a page-counted slot can be picked together; one at a time
                    // still works.
                    multiple={byPage}
                    disabled={full}
                    disabledReason={t(words.full)}
                  />
                )}
              </div>
              {forType.length ? (
                <div className="space-y-1">
                  {forType.map((d) => (
                    <DocumentRow key={d.id} doc={d} />
                  ))}
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">{t("workflow.noFile")}</p>
              )}
            </div>
          );
        })}
    </>
  );
}
