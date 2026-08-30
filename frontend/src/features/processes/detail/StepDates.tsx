import { useTranslation } from "react-i18next";

import { FieldError } from "@/components/ui/field-error";
import { DateField } from "@/components/ui/date-field";
import { Label } from "@/components/ui/label";

import type { StepFields } from "./useStepFields";

type DateField = "start_date" | "end_date";

/**
 * The start/end pair every step carries (UC-050, UC-078).
 *
 * Shared by all five steps: the office dates the first and last the same way as the institute
 * steps, and the compiled cover sheet prints a row per step — so a step whose dates could not be
 * entered printed an empty line on a signed document.
 */
export function StepDates({
  fields: { field, errors, clear },
  canEdit,
  hint,
  // Step 5 is the roll-up: it holds no work of its own, so it shows only the closing date and
  // an empty "start" box there would just ask the office a question with no answer (UC-078).
  show = ["start_date", "end_date"],
}: {
  /** The step row's shared autosave queue, from `useStepFields`. */
  fields: StepFields;
  canEdit: boolean;
  hint?: string;
  show?: DateField[];
}) {
  const { t } = useTranslation();

  // `DateField` reports a date only once the three boxes name a real day, so nothing half-typed
  // reaches the queue any more — the year 2026 no longer arrives as 2, 20 and 202 on its way
  // (UC-072, closed at the source by UC-108).
  const edit = (name: DateField) => (value: string) => {
    clear(name);
    field.set(name, value || null);
  };

  return (
    <div className="space-y-1">
      <div className="grid gap-3 sm:grid-cols-2">
        {show.map((name) => (
          <div key={name} className="space-y-1">
            <Label className="text-xs">
              {t(name === "start_date" ? "workflow.startDate" : "workflow.endDate")}
            </Label>
            <DateField
              value={field.value(name) ?? ""}
              disabled={!canEdit}
              className="h-9"
              invalid={Boolean(errors[name])}
              onChange={edit(name)}
              onBlur={field.flush}
            />
            <FieldError message={errors[name]} />
          </div>
        ))}
      </div>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}
