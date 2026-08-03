import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toaster";
import { useListCategoriesQuery } from "@/features/categories/categoriesApi";
import { apiErrorMessage } from "@/lib/apiError";

import { useUpdateProcessMutation } from "../processesApi";
import type { ProcessDetail } from "../types";

export type LandField = "category" | "land_id" | "land_address";

/**
 * The case header's land fields, rendered wherever a step needs them. **`land_id` is one field with
 * one stored value** (`Process.land_id`) shown in two steps: offered in Step 1 for a lawyer who
 * already knows it, and required in Step 4, where the registration institutes produce it (UC-041).
 * Sharing the form is what keeps the two places from drifting into two different save paths.
 */
export function LandDetailsForm({
  process,
  canEdit,
  fields,
  idPrefix,
  landIdRequired = false,
}: {
  process: ProcessDetail;
  canEdit: boolean;
  fields: LandField[];
  idPrefix: string;
  landIdRequired?: boolean;
}) {
  const { t } = useTranslation();
  const { data: categories } = useListCategoriesQuery(undefined, {
    skip: !fields.includes("category"),
  });
  const [update, { isLoading }] = useUpdateProcessMutation();

  const initialCategory = process.category ? String(process.category) : "";
  const [category, setCategory] = useState(initialCategory);
  const [landId, setLandId] = useState(process.land_id);
  const [landAddress, setLandAddress] = useState(process.land_address);

  useEffect(() => {
    setCategory(process.category ? String(process.category) : "");
    setLandId(process.land_id);
    setLandAddress(process.land_address);
  }, [process.category, process.land_id, process.land_address, process.id]);

  // Only the fields this instance renders may count as dirty, or Step 4 would offer to save a
  // category it never showed.
  const dirty =
    (fields.includes("category") && category !== initialCategory) ||
    (fields.includes("land_id") && landId !== process.land_id) ||
    (fields.includes("land_address") && landAddress !== process.land_address);

  const save = async () => {
    try {
      await update({
        id: process.id,
        version: process.version,
        ...(fields.includes("category") ? { category: category ? Number(category) : null } : {}),
        ...(fields.includes("land_id") ? { land_id: landId } : {}),
        ...(fields.includes("land_address") ? { land_address: landAddress } : {}),
      }).unwrap();
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(apiErrorMessage(err, t("common.saveError")));
    }
  };

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2">
        {fields.includes("category") && (
          <div className="space-y-1.5">
            <Label htmlFor={`${idPrefix}-category`}>{t("processes.category")}</Label>
            <Select
              id={`${idPrefix}-category`}
              value={category}
              disabled={!canEdit}
              onChange={(e) => setCategory(e.target.value)}
            >
              <option value="">{t("common.none")}</option>
              {(categories ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.code} — {c.name}
                </option>
              ))}
            </Select>
          </div>
        )}
        {fields.includes("land_id") && (
          <div className="space-y-1.5">
            <Label htmlFor={`${idPrefix}-landid`}>
              {t("workflow.landId")}{" "}
              <span className="text-xs font-normal text-muted-foreground">
                {landIdRequired ? t("workflow.requiredHere") : t("workflow.optionalHere")}
              </span>
            </Label>
            <Input
              id={`${idPrefix}-landid`}
              value={landId}
              disabled={!canEdit}
              onChange={(e) => setLandId(e.target.value)}
              placeholder={t("workflow.landIdPlaceholder")}
            />
          </div>
        )}
        {fields.includes("land_address") && (
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor={`${idPrefix}-address`}>{t("workflow.landAddress")}</Label>
            <Input
              id={`${idPrefix}-address`}
              value={landAddress}
              disabled={!canEdit}
              onChange={(e) => setLandAddress(e.target.value)}
              placeholder={t("workflow.landAddressPlaceholder")}
            />
          </div>
        )}
      </div>
      {canEdit && (
        <Button size="sm" onClick={save} disabled={isLoading || !dirty}>
          {isLoading && <Spinner />}
          {t("workflow.saveLand")}
        </Button>
      )}
    </>
  );
}
