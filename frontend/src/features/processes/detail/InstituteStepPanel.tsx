import { Plus } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/lib/toast";
import { instituteLabel, useListInstitutesQuery } from "@/features/institutes/institutesApi";
import { useListLawyersQuery } from "@/features/users/lawyersApi";
import { apiErrorMessage } from "@/lib/apiError";

import { useCreateEntryMutation } from "../processesApi";
import type { ProcessDetail } from "../types";
import { InstituteEntryCard } from "./InstituteEntryCard";
import { LandDetailsForm } from "./LandDetailsForm";
import { StepDates } from "./StepDates";
import { StepDocumentSlots } from "./StepDocumentSlots";
import { useStepFields } from "./useStepFields";

// Steps 2–4: fixed institutes from the shared enum, plus Step-3 out-of-city custom rows (§5.1, §5.6).
export function InstituteStepPanel({
  process,
  step,
  canEdit,
}: {
  process: ProcessDetail;
  step: number;
  canEdit: boolean;
}) {
  const { t } = useTranslation();
  // Both feed dropdowns. Without the loading flags the selects render EMPTY on a slow link, which
  // a lawyer reads as "there are no institutes" rather than "still loading" (UC-006).
  const { data: institutes, isLoading: loadingInstitutes } = useListInstitutesQuery();
  const { data: lawyers, isLoading: loadingLawyers } = useListLawyersQuery();
  const [createEntry] = useCreateEntryMutation();
  const stepFields = useStepFields(process, step);
  const { field } = stepFields;

  const entries = process.institute_entries.filter((e) => e.step_number === step);
  const loadingVocabulary = loadingInstitutes || loadingLawyers;
  const fixed = (institutes ?? []).filter((i) => i.step === step);
  const customs = entries.filter((e) => e.is_custom);
  const lawyerList = lawyers ?? [];

  const addFixed = async (code: string) => {
    try {
      await createEntry({ process: process.id, step_number: step, institute_code: code }).unwrap();
    } catch (err) {
      toast.error(apiErrorMessage(err, t("common.saveError")));
    }
  };

  const addCustom = async () => {
    try {
      await createEntry({
        process: process.id,
        step_number: 3,
        is_custom: true,
        custom_name: t("workflow.newCustom"),
      }).unwrap();
    } catch (err) {
      toast.error(apiErrorMessage(err, t("common.saveError")));
    }
  };

  return (
    <div className="space-y-4">
      {/* Every institute step carries dates, not just step 2 (UC-050). The start is stamped when
          the lawyer proceeds into the step and stays editable, since a date typed by hand is
          usually a correction. Without these the compiled cover sheet had nothing to print for
          steps 3 and 4 (UC-058a). */}
      <StepDates fields={stepFields} canEdit={canEdit} />

      {loadingVocabulary && (
        <div className="space-y-2">
          <Skeleton className="h-11 w-full" />
          <Skeleton className="h-11 w-full" />
        </div>
      )}

      {fixed.map((inst) => {
        const entry = entries.find((e) => !e.is_custom && e.institute_code === inst.code);
        if (entry) {
          return (
            <InstituteEntryCard
              key={inst.code}
              process={process}
              entry={entry}
              label={instituteLabel(inst)}
              lawyers={lawyerList}
              canEdit={canEdit}
            />
          );
        }
        return (
          <div
            key={inst.code}
            className="flex items-center justify-between rounded-lg border border-dashed border-border px-3 py-2.5 text-sm"
          >
            <span className="text-muted-foreground">{instituteLabel(inst)}</span>
            {canEdit && (
              <Button type="button" variant="outline" size="sm" onClick={() => addFixed(inst.code)}>
                <Plus className="size-4" />
                {t("workflow.addEntry")}
              </Button>
            )}
          </div>
        );
      })}

      {/* Step 4 is the only institute step that also owns a field and a document: the registration
          institutes are what produce the land number and the real-estate paper (UC-037, UC-041). */}
      {step === 4 && (
        <>
          {/* Above the land card, not inside it (UC-099): the municipality form is a paper the
              office files, so it belongs with the institutes' own file inputs directly above it —
              every upload on the step reads as one run, and the land number closes the step. */}
          <StepDocumentSlots process={process} step={4} canEdit={canEdit} />
          <div className="space-y-4 rounded-lg bg-muted/40 p-3">
            {/* The address rides along with the number (UC-049) — same stored value as Step 1,
                shown here because this is where the registration institutes settle both. */}
            <LandDetailsForm
              process={process}
              canEdit={canEdit}
              idPrefix="s4"
              fields={["land_id", "land_address"]}
              landIdRequired
            />
          </div>
        </>
      )}

      {step === 3 && (
        <div className="space-y-3 rounded-lg bg-muted/40 p-3">
          <label className="flex items-center gap-2 text-sm font-medium">
            <Checkbox
              checked={field.value("out_of_city_flag")}
              disabled={!canEdit}
              onChange={(e) => field.commit("out_of_city_flag", e.target.checked)}
            />
            {t("workflow.outOfCity")}
          </label>
          {field.value("out_of_city_flag") && (
            <div className="space-y-3">
              {customs.map((entry) => (
                <InstituteEntryCard
                  key={entry.id}
                  process={process}
                  entry={entry}
                  label={entry.custom_name}
                  lawyers={lawyerList}
                  canEdit={canEdit}
                />
              ))}
              {canEdit && (
                <Button type="button" variant="outline" size="sm" onClick={addCustom}>
                  <Plus className="size-4" />
                  {t("workflow.addCustom")}
                </Button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
