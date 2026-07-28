import { AlertTriangle, Info } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toaster";
import { useListCategoriesQuery } from "@/features/categories/categoriesApi";
import { DocumentRow } from "@/features/documents/DocumentRow";
import { DocumentUpload } from "@/features/documents/DocumentUpload";
import { useListDocumentTypesQuery } from "@/features/documents/documentTypesApi";
import { apiErrorMessage } from "@/lib/apiError";

import { useUpdateProcessMutation } from "../processesApi";
import { ClientDetailsPanel } from "./ClientDetailsPanel";
import { GeneratedLetterPanel } from "./GeneratedLetterPanel";
import type { ProcessDetail } from "../types";

// Step 1: editable header (category + land id/address) plus the client papers (§5.1). The
// document types come from the shared vocabulary so the slots always match what the backend
// requires for completion (§6.7).
export function Step1Panel({
  process,
  canEdit,
}: {
  process: ProcessDetail;
  canEdit: boolean;
}) {
  const { t } = useTranslation();
  const { data: categories } = useListCategoriesQuery({});
  const { data: documentTypes } = useListDocumentTypesQuery();
  const [update, { isLoading }] = useUpdateProcessMutation();
  const docs = process.documents.filter((d) => d.step_number === 1);
  const types = documentTypes ?? [];
  // Generating the letter is unlocked by finishing Step 1, never the other way round (§0).
  const stepComplete =
    (process.steps.find((s) => s.step_number === 1)?.missing.length ?? 1) === 0;

  const [category, setCategory] = useState<string>(
    process.category ? String(process.category) : "",
  );
  const [landId, setLandId] = useState(process.land_id);
  const [landAddress, setLandAddress] = useState(process.land_address);

  useEffect(() => {
    setCategory(process.category ? String(process.category) : "");
    setLandId(process.land_id);
    setLandAddress(process.land_address);
  }, [process.category, process.land_id, process.land_address, process.id]);

  const dirty =
    category !== (process.category ? String(process.category) : "") ||
    landId !== process.land_id ||
    landAddress !== process.land_address;

  const save = async () => {
    try {
      await update({
        id: process.id,
        version: process.version,
        category: category ? Number(category) : null,
        land_id: landId,
        land_address: landAddress,
      }).unwrap();
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(apiErrorMessage(err, t("common.saveError")));
    }
  };

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

      <ClientDetailsPanel client={process.client_detail} canEdit={canEdit} />

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="s1-category">{t("processes.category")}</Label>
          <Select
            id="s1-category"
            value={category}
            disabled={!canEdit}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="">{t("common.none")}</option>
            {(categories?.results ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.code} — {c.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="s1-landid">{t("workflow.landId")}</Label>
          <Input
            id="s1-landid"
            value={landId}
            disabled={!canEdit}
            onChange={(e) => setLandId(e.target.value)}
            placeholder={t("workflow.landIdPlaceholder")}
          />
        </div>
        <div className="space-y-1.5 sm:col-span-2">
          <Label htmlFor="s1-address">{t("workflow.landAddress")}</Label>
          <Input
            id="s1-address"
            value={landAddress}
            disabled={!canEdit}
            onChange={(e) => setLandAddress(e.target.value)}
            placeholder={t("workflow.landAddressPlaceholder")}
          />
        </div>
      </div>
      {canEdit && (
        <Button size="sm" onClick={save} disabled={isLoading || !dirty}>
          {isLoading && <Spinner />}
          {t("workflow.saveLand")}
        </Button>
      )}

      {types
        .filter(
          (dt) =>
            dt.step === 1 &&
            // Generated letters are output, not something anyone uploads.
            !dt.generated &&
            // A conditional slot still shows while it holds a file: a client who stops being
            // married would otherwise leave an uploaded spouse ID on disk with no way to see
            // or remove it.
            (!dt.only_when_married ||
              process.client_detail.is_married ||
              docs.some((d) => d.document_type === dt.code)),
        )
        .map(({ code: type, display_key }) => {
          const forType = docs.filter((d) => d.document_type === type);
          return (
            <div key={type} className="space-y-2">
              <div className="flex items-center justify-between gap-2">
                <Label>{t(display_key)}</Label>
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
                <p className="text-xs text-muted-foreground">
                  {t("workflow.noFile")}
                </p>
              )}
            </div>
          );
        })}

      <GeneratedLetterPanel
        processId={process.id}
        documents={docs}
        generatedTypes={types.filter((dt) => dt.generated)}
        canGenerate={canEdit}
        stepComplete={stepComplete}
      />
    </div>
  );
}
