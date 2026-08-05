import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toaster";
import { useListCategoriesQuery } from "@/features/categories/categoriesApi";

import { codeErrorMessage } from "../codeError";

import { useUpdateProcessMutation } from "../processesApi";
import type { ProcessDetail } from "../types";

export type LandField = "unique_code" | "category" | "land_id" | "land_address";

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
  const own = (categories ?? []).find((c) => c.id === process.category);
  const categoryLabel = own ? `${own.code} — ${own.name}` : "";
  const [update, { isLoading }] = useUpdateProcessMutation();

  const [landId, setLandId] = useState(process.land_id);
  const [landAddress, setLandAddress] = useState(process.land_address);
  const [code, setCode] = useState(process.unique_code);

  useEffect(() => {
    setLandId(process.land_id);
    setLandAddress(process.land_address);
    setCode(process.unique_code);
  }, [process.land_id, process.land_address, process.unique_code, process.id]);

  // Only the fields this instance renders may count as dirty, or Step 4 would offer to save a
  // category it never showed.
  const dirty =
    (fields.includes("land_id") && landId !== process.land_id) ||
    (fields.includes("land_address") && landAddress !== process.land_address) ||
    (fields.includes("unique_code") && code !== process.unique_code);

  const save = async () => {
    try {
      await update({
        id: process.id,
        version: process.version,
        ...(fields.includes("land_id") ? { land_id: landId } : {}),
        ...(fields.includes("land_address") ? { land_address: landAddress } : {}),
        ...(fields.includes("unique_code") && code !== process.unique_code
          ? { unique_code: code.trim() }
          : {}),
      }).unwrap();
      toast.success(t("common.saved"));
    } catch (err) {
      // A refused case number is the one failure here a lawyer causes by simply mistyping, so it
      // is named in their own language rather than left as the server's English (UC-062).
      toast.error(codeErrorMessage(err, t, t("common.saveError")));
    }
  };

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2">
        {/* The office's own case number. Issued automatically at creation, and correctable since
            UC-062 — the office sets where the sequence resumes. The server still refuses a number
            already issued or one from another category, so a bad edit comes back as a 400 rather
            than landing. `dir="ltr"` because it is quoted on paper left-to-right. */}
        {fields.includes("unique_code") && (
          <div className="space-y-1.5">
            <Label htmlFor={`${idPrefix}-code`}>
              {t("workflow.uniqueCode")}{" "}
              <span className="text-xs font-normal text-muted-foreground">
                {t("workflow.neverReused")}
              </span>
            </Label>
            {canEdit ? (
              <Input
                id={`${idPrefix}-code`}
                dir="ltr"
                className="font-mono"
                value={code}
                onChange={(e) => setCode(e.target.value)}
              />
            ) : (
              <p
                id={`${idPrefix}-code`}
                dir="ltr"
                className="rounded-md border border-input bg-muted/40 px-3 py-2 font-mono text-sm text-start"
              >
                {process.unique_code || t("common.none")}
              </p>
            )}
          </div>
        )}
        {/* Shown, never edited: a case's category is fixed once it is created — moving one means
            opening a new case in the other category (UC-059). The server refuses a change, so
            offering a dropdown here would only invite a 400. */}
        {fields.includes("category") && (
          <div className="space-y-1.5">
            <Label htmlFor={`${idPrefix}-category`}>
              {t("processes.category")}{" "}
              <span className="text-xs font-normal text-muted-foreground">
                {t("workflow.fixedAtCreation")}
              </span>
            </Label>
            <p
              id={`${idPrefix}-category`}
              className="rounded-md border border-input bg-muted/40 px-3 py-2 text-sm"
            >
              {categoryLabel || t("common.none")}
            </p>
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
