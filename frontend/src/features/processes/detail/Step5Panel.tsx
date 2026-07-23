import { CheckCircle2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toaster";
import { apiErrorMessage } from "@/lib/apiError";

import { useCompleteProcessMutation } from "../processesApi";
import type { ProcessDetail } from "../types";

// Step 5: mark the case complete. Blocks on missing files unless an admin forces it (§5, §10.3).
export function Step5Panel({
  process,
  canEdit,
  isAdmin,
}: {
  process: ProcessDetail;
  canEdit: boolean;
  isAdmin: boolean;
}) {
  const { t } = useTranslation();
  const [complete, { isLoading }] = useCompleteProcessMutation();
  const done = process.overall_status === "complete";

  const run = async (force: boolean) => {
    try {
      await complete({ id: process.id, version: process.version, force }).unwrap();
      toast.success(t("workflow.completed"));
    } catch (err) {
      toast.error(apiErrorMessage(err, t("workflow.missingFiles")));
    }
  };

  if (done) {
    return (
      <div className="flex items-center gap-2 rounded-md bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-400">
        <CheckCircle2 className="size-4 shrink-0" />
        {t("workflow.caseComplete")}
      </div>
    );
  }

  return (
    <div className="space-y-3">
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
