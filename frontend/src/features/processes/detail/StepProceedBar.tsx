import { ArrowRight, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Dialog, DialogFooter } from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toaster";
import { instituteLabel, useListInstitutesQuery } from "@/features/institutes/institutesApi";
import { useNum } from "@/hooks/useNum";
import { apiErrorMessage } from "@/lib/apiError";

import { useAdvanceStepMutation } from "../processesApi";
import type { ProcessDetail } from "../types";

// Explicit "proceed" that unlocks the next step (§5.2). Proceeding with an unfinished step is
// allowed — the dialog just spells out what is still missing first.
export function StepProceedBar({
  process,
  step,
  missing,
}: {
  process: ProcessDetail;
  step: number;
  missing: string[];
}) {
  const { t } = useTranslation();
  const num = useNum();
  const [open, setOpen] = useState(false);
  const { data: institutes } = useListInstitutesQuery();
  const [advance, { isLoading }] = useAdvanceStepMutation();

  // Server sends stable codes (`institute:<code>`, `doc:<type>`, or a bare field name); each maps
  // onto an existing translation so nothing is hard-coded twice. `step:<n>` codes exist too but
  // only ever come from Step 5, which has no Proceed bar. An unknown code degrades to its own
  // text rather than leaking a raw i18n key into the dialog.
  const labelFor = (code: string): string => {
    const [kind, value] = code.split(":");
    if (kind === "institute") {
      const inst = institutes?.find((i) => i.code === value);
      return inst ? instituteLabel(inst) : value;
    }
    if (kind === "doc") return t(`workflow.docType.${value}`, { defaultValue: value });
    return t(`workflow.missing.${code}`, { defaultValue: code });
  };

  const confirm = async () => {
    try {
      await advance({ id: process.id, version: process.version }).unwrap();
      toast.success(t("workflow.proceeded", { n: num(step + 1) }));
      setOpen(false);
    } catch (err) {
      toast.error(apiErrorMessage(err, t("common.saveError")));
    }
  };

  return (
    <>
      <div className="mt-4 flex justify-end border-t border-border pt-4">
        <Button onClick={() => setOpen(true)}>
          {t("workflow.proceedTo", { n: num(step + 1) })}
          <ArrowRight className="size-4 rtl:rotate-180" />
        </Button>
      </div>

      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title={t("workflow.proceedTitle", { n: num(step + 1) })}
        className="max-w-md"
      >
        {missing.length > 0 ? (
          <div className="space-y-3 text-sm">
            <div className="flex items-start gap-2 text-amber-700 dark:text-amber-400">
              <TriangleAlert className="mt-0.5 size-4 shrink-0" />
              <span>{t("workflow.proceedIncomplete", { n: num(step) })}</span>
            </div>
            <ul className="list-disc space-y-1 ps-6 text-muted-foreground">
              {missing.map((code) => (
                <li key={code}>{labelFor(code)}</li>
              ))}
            </ul>
            <p className="text-muted-foreground">{t("workflow.proceedAnyway")}</p>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            {t("workflow.proceedConfirm", { n: num(step + 1) })}
          </p>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)} disabled={isLoading}>
            {t("common.cancel")}
          </Button>
          <Button onClick={confirm} disabled={isLoading}>
            {isLoading && <Spinner />}
            {t("workflow.proceed")}
          </Button>
        </DialogFooter>
      </Dialog>
    </>
  );
}
