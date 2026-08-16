import { useTranslation } from "react-i18next";

import { toast } from "@/lib/toast";
import { apiErrorMessage } from "@/lib/apiError";
import { labeller } from "@/lib/fieldLabels";
import { useAutosave } from "@/hooks/useAutosave";
import { useFieldErrors } from "@/hooks/useFieldErrors";

import { useSaveStepMutation } from "../processesApi";
import type { ProcessDetail } from "../types";

/**
 * Everything one step row autosaves, as a single queue.
 *
 * One hook per step rather than one per control: these fields all live on the same row behind the
 * same `version` (§12 optimistic locking), so two independent savers editing them back to back
 * would send two patches against the same version and the second would come back 409.
 */
export function useStepFields(process: ProcessDetail, step: number) {
  const { t } = useTranslation();
  const [saveStep] = useSaveStepMutation();
  const { errors, setFromError, clear, clearAll } = useFieldErrors();

  const stepRow = process.steps.find((s) => s.step_number === step)!;

  const save = async (fields: Record<string, unknown>) => {
    try {
      await saveStep({ process: process.id, step, version: stepRow.version, ...fields }).unwrap();
      clearAll();
    } catch (err) {
      // The dates carry a rule of their own — an end before a start (§5.2) — and both print on
      // the compiled cover sheet, so the rejected one must be visible on the field itself.
      setFromError(err);
      toast.error(apiErrorMessage(err, t("common.saveError"), labeller(t), t));
    }
  };

  const field = useAutosave({
    saved: {
      start_date: stepRow.start_date,
      end_date: stepRow.end_date,
      out_of_city_flag: stepRow.out_of_city_flag,
    },
    onSave: save,
  });

  return { stepRow, field, errors, clear };
}

export type StepFields = ReturnType<typeof useStepFields>;
