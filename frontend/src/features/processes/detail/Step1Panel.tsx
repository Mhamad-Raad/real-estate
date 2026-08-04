import { AlertTriangle, Info } from "lucide-react";
import { useTranslation } from "react-i18next";

import { FormSection } from "@/components/ui/separator";
import { useListDocumentTypesQuery } from "@/features/documents/documentTypesApi";

import { ClientDetailsPanel } from "./ClientDetailsPanel";
import { GeneratedLetterPanel } from "./GeneratedLetterPanel";
import { LandDetailsForm } from "./LandDetailsForm";
import { StepDocumentSlots } from "./StepDocumentSlots";
import type { ProcessDetail } from "../types";

// Step 1: editable header (category + land id/address) plus the client papers (§5.1). The land
// number is offered here but only required in Step 4 (UC-041), and the real-estate paper moved
// there entirely (UC-037), so this step now asks only for what the office holds on day one.
export function Step1Panel({
  process,
  canEdit,
}: {
  process: ProcessDetail;
  canEdit: boolean;
}) {
  const { t } = useTranslation();
  const { data: documentTypes } = useListDocumentTypesQuery();
  const docs = process.documents.filter((d) => d.step_number === 1);
  const types = documentTypes ?? [];
  // The letter renders names and birth years and nothing else (§6.6), so the names are the only
  // real precondition — it used to wait on the whole step, which after UC-037/UC-041 it must not.
  const client = process.client_detail;
  const hasNames =
    Boolean(client.full_name.trim()) && (!client.is_married || Boolean(client.spouse_name?.trim()));

  return (
    <div className="space-y-5">
      {process.duplicate_flagged && (
        <div className="flex items-center gap-2 rounded-md bg-amber-500/10 px-3 py-2 text-sm text-amber-700 dark:text-amber-400">
          <AlertTriangle className="size-4 shrink-0" />
          {t("workflow.flaggedNote")}
        </div>
      )}

      {/* Advisory only — deliberately muted, since this never blocks the step (§5.7). */}
      {process.similar_name_flagged && !process.duplicate_flagged && (
        <div className="flex items-center gap-2 rounded-md bg-muted px-3 py-2 text-sm text-muted-foreground">
          <Info className="size-4 shrink-0" />
          {t("workflow.similarNameNote")}
        </div>
      )}

      <FormSection title={t("workflow.sectionBeneficiary")}>
        <ClientDetailsPanel client={process.client_detail} canEdit={canEdit} />
      </FormSection>

      <FormSection title={t("workflow.sectionLand")}>
        <LandDetailsForm
          process={process}
          canEdit={canEdit}
          idPrefix="s1"
          fields={["unique_code", "category", "land_id", "land_address"]}
        />
      </FormSection>

      <FormSection title={t("workflow.sectionPapers")}>
        <StepDocumentSlots process={process} step={1} canEdit={canEdit} />
      </FormSection>

      <FormSection title={t("workflow.sectionLetter")}>
        <GeneratedLetterPanel
          processId={process.id}
          documents={docs}
          generatedTypes={types.filter((dt) => dt.generated)}
          canGenerate={canEdit}
          hasNames={hasNames}
        />
      </FormSection>
    </div>
  );
}
