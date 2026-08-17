import { CheckCircle2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/lib/toast";
import { apiErrorMessage } from "@/lib/apiError";

import { useCompleteProcessMutation } from "../processesApi";
import type { ProcessDetail } from "../types";
import { StepDates } from "./StepDates";
import { useStepFields } from "./useStepFields";

// Step 5: mark the case complete. Blocks on missing files unless an admin forces it (§5, §10.3).
export function Step5Panel({
  process,
  canEdit,
  isAdmin,
  onCompleted,
}: {
  process: ProcessDetail;
  canEdit: boolean;
  isAdmin: boolean;
  /** Closing the case is what compiles it (UC-086) — the panel below runs off this press. */
  onCompleted: () => void;
}) {
  const { t } = useTranslation();
  const [complete, { isLoading }] = useCompleteProcessMutation();
  const stepFields = useStepFields(process, 5);
  const done = process.overall_status === "complete";

  const run = async (force: boolean) => {
    try {
      await complete({ id: process.id, version: process.version, force }).unwrap();
      toast.success(t("workflow.completed"));
      onCompleted();
    } catch (err) {
      toast.error(apiErrorMessage(err, t("workflow.missingFiles")));
    }
  };

  // Step 5 carries a closing date and nothing else (UC-078). It is the roll-up step — it holds no
  // work of its own to have started — and the date is stamped by marking the case complete, since
  // nothing proceeds past step 5. Editable all the same: a case closed late should be able to
  // carry the day the work actually finished, like every other stamped date here.
  const dates = (
    <StepDates
      fields={stepFields}
      show={["end_date"]}
      canEdit={canEdit}
      hint={t("workflow.endDateOnDone")}
    />
  );

  if (done) {
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-2 rounded-md bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-400">
          <CheckCircle2 className="size-4 shrink-0" />
          {t("workflow.caseComplete")}
        </div>
        {dates}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {dates}
      <p className="text-sm text-muted-foreground">{t("workflow.completeHint")}</p>
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => run(false)} disabled={isLoading || !canEdit}>
          {isLoading && <Spinner />}
          {t("workflow.markComplete")}
        </Button>
        {isAdmin && (
          <Button variant="outline" onClick={() => run(true)} disabled={isLoading}>
            {t("workflow.forceComplete")}
          </Button>
        )}
      </div>
    </div>
  );
}
