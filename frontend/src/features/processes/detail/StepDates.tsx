import { useTranslation } from "react-i18next";

import { FieldError } from "@/components/ui/field-error";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { isSettledDate } from "@/hooks/useAutosave";

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
  fields: { stepRow, field, errors, clear },
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

  const edit = (name: DateField) => (value: string) => {
    clear(name);
    // Held on screen while it is still being typed and only sent once it settles, or the year
    // 2026 would be saved four times on its way through 0002, 0020 and 0202 (UC-072).
    field.set(name, value || null, isSettledDate(value));
  };

  // Leaving a half-typed year behind would show a value that was never stored; the field goes
  // back to what the case actually holds rather than lying about being saved.
  const leave = (name: DateField) => () => {
    if (!isSettledDate(field.value(name) ?? "")) field.set(name, stepRow[name], false);
    field.flush();
  };

  return (
    <div className="space-y-1">
      <div className="grid gap-3 sm:grid-cols-2">
        {show.map((name) => (
          <div key={name} className="space-y-1">
            <Label className="text-xs">
              {t(name === "start_date" ? "workflow.startDate" : "workflow.endDate")}
            </Label>
            <Input
              type="date"
              value={field.value(name) ?? ""}
              disabled={!canEdit}
              className="h-9"
              invalid={Boolean(errors[name])}
              onChange={(e) => edit(name)(e.target.value)}
              onBlur={leave(name)}
            />
            <FieldError message={errors[name]} />
          </div>
        ))}
      </div>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}
