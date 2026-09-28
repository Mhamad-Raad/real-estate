import { useTranslation } from "react-i18next";

import { Spinner } from "@/components/ui/spinner";
import { filterName } from "@/lib/name";
import { filterPid } from "@/lib/pid";

import { CardPreview } from "./CardPreview";
import { CardSection } from "./CardSection";
import { DraftFieldInput } from "./DraftFieldInput";
import { SPOUSE_FIELDS, type SpouseValues } from "./spouseFields";
import type { CardScan } from "./types";

// The spouse's own card, in its own box under the beneficiary's: their scan beside their fields,
// so neither person is checked against the other's card (§6.6, UC-128). Three of these fields are
// printed on the eligibility letter and the database requires them together; `spouse_pid` is not
// printed at all — it exists so a couple cannot be allocated land twice (§5.7).
// The same keystroke rules as the beneficiary's own card fields and the intake form's spouse block.
const FILTERS: Partial<Record<keyof SpouseValues, (raw: string) => string>> = {
  spouse_name: filterName,
  spouse_mother_full_name: filterName,
  spouse_pid: filterPid,
};

export function SpouseSection({
  scanId,
  scan,
  reading,
  values,
  onChange,
  errors = {},
  onFieldEdit,
}: {
  /** The staged spouse card — shown while it is still being read, before `scan` settles. */
  scanId: number | null;
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
    <CardSection title={t("cardScan.spouseSection")} aside={reading ? <Spinner /> : null}>
      {scanId != null ? <CardPreview scanId={scanId} /> : <div />}

      <div className="space-y-4">
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
            filter={FILTERS[name]}
            onChange={(value) => {
              onFieldEdit?.(name);
              onChange({ ...values, [name]: value });
            }}
          />
        ))}
        <p className="text-xs text-muted-foreground">{t("cardScan.spousePidHint")}</p>
      </div>
    </CardSection>
  );
}
