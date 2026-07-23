import { AlertTriangle } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Label } from "@/components/ui/label";
import { DocumentRow } from "@/features/documents/DocumentRow";
import { DocumentUpload } from "@/features/documents/DocumentUpload";
import type { ProcessDetail } from "../types";

// Step 1: the three client papers drive completion; header fields were set at creation (§5.1).
const STEP1_DOC_TYPES = ["ClientID", "RealEstate", "SignedAgreement"];

export function Step1Panel({ process, canEdit }: { process: ProcessDetail; canEdit: boolean }) {
  const { t } = useTranslation();
  const docs = process.documents.filter((d) => d.step_number === 1);

  return (
    <div className="space-y-5">
      {process.duplicate_flagged && (
        <div className="flex items-center gap-2 rounded-md bg-amber-500/10 px-3 py-2 text-sm text-amber-700 dark:text-amber-400">
          <AlertTriangle className="size-4 shrink-0" />
          {t("workflow.flaggedNote")}
        </div>
      )}

      <div className="grid gap-3 text-sm sm:grid-cols-2">
        <div className="flex justify-between rounded-md bg-muted/50 px-3 py-2">
          <span className="text-muted-foreground">{t("processes.category")}</span>
          <span>{process.category ? t("workflow.set") : t("workflow.notSet")}</span>
        </div>
        <div className="flex justify-between rounded-md bg-muted/50 px-3 py-2">
          <span className="text-muted-foreground">{t("processes.parcel")}</span>
          <span>{process.parcel ? t("workflow.set") : t("workflow.notSet")}</span>
        </div>
      </div>

      {STEP1_DOC_TYPES.map((type) => {
        const forType = docs.filter((d) => d.document_type === type);
        return (
          <div key={type} className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <Label>{t(`workflow.docType.${type}`)}</Label>
              {canEdit && (
                <DocumentUpload
                  process={process.id}
                  step={1}
                  documentType={type}
                  label={t("workflow.import")}
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
    </div>
  );
}
