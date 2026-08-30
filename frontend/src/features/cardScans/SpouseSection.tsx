import { useTranslation } from "react-i18next";

import { Spinner } from "@/components/ui/spinner";

import { DraftFieldInput } from "./DraftFieldInput";
import { SPOUSE_FIELDS, type SpouseValues } from "./spouseFields";
import type { CardScan } from "./types";

// The spouse's own card, reviewed beside the beneficiary's (§6.6). Three of these fields are
// printed on the eligibility letter and the database requires them together; `spouse_pid` is not
// printed at all — it exists so a couple cannot be allocated land twice (§5.7).
export function SpouseSection({
  scan,
  reading,
  values,
  onChange,
  errors = {},
  onFieldEdit,
}: {
  scan: CardScan | null;
  reading: boolean;
  values: SpouseValues;
  onChange: (values: SpouseValues) => void;
  /** Per-field server errors — `spouse_date_of_birth` is validated like the beneficiary's own. */
  errors?: Record<string, string>;
  onFieldEdit?: (field: string) => void;
}) {
  const { t } = useTranslation();
  const fields = scan?.draft?.fields ?? {};

  return (
    <div className="space-y-4 rounded-md border border-border p-4">
      <div className="flex items-center gap-2">
        <p className="text-sm font-medium">{t("cardScan.spouseSection")}</p>
        {reading ? <Spinner /> : null}
      </div>

      {scan?.status === "failed" ? (
        <p className="text-xs text-warning">{t("cardScan.readingFailedBody")}</p>
      ) : null}

      {SPOUSE_FIELDS.map(({ name, from }) => (
        <DraftFieldInput
          key={name}
          name={name}
          label={t(`cardScan.field.${name}`)}
          value={values[name]}
          draft={fields[from]}
          type={name === "spouse_date_of_birth" ? "date" : "text"}
          // The letter prints the first three, so they are required; the dedup key is not.
          required={name !== "spouse_pid"}
          error={errors[name]}
          onChange={(value) => {
            onFieldEdit?.(name);
            onChange({ ...values, [name]: value });
          }}
        />
      ))}
      <p className="text-xs text-muted-foreground">{t("cardScan.spousePidHint")}</p>
    </div>
  );
}
