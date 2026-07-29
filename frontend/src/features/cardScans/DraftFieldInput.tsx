import { AlertTriangle, CheckCircle2, PencilLine } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

import type { DraftField } from "./types";

// Below this the engine was guessing more than reading — the field is worth a second look.
const LOW_CONFIDENCE = 70;

/** One editable field, marked with where its value came from and how sure the engine was. */
export function DraftFieldInput({
  name,
  label,
  value,
  draft,
  type = "text",
  required = false,
  onChange,
}: {
  name: string;
  label: string;
  value: string;
  draft?: DraftField;
  type?: string;
  required?: boolean;
  onChange: (value: string) => void;
}) {
  const { t } = useTranslation();
  // Edited away from what OCR proposed — the human's value, and no longer the engine's claim.
  const corrected = Boolean(draft?.value) && draft?.value !== value;
  // Only a value the engine actually produced can be uncertain. A blank read still returns every
  // field at confidence 0, and flagging those would put a warning on every empty box — noise at
  // exactly the moment the lawyer is typing the card in by hand.
  const uncertain =
    Boolean(draft?.value) && !draft?.verified && (draft?.confidence ?? 0) < LOW_CONFIDENCE;

  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
        <Label htmlFor={name}>
          {label}
          {required ? <span className="text-destructive"> *</span> : null}
        </Label>
        {draft?.value ? <SourceMark draft={draft} corrected={corrected} /> : null}
      </div>

      <Input
        id={name}
        type={type}
        value={value}
        required={required}
        onChange={(e) => onChange(e.target.value)}
        // Latin digits and dates scramble inside an RTL paragraph without an explicit direction.
        dir={type === "date" || name === "pid" ? "ltr" : undefined}
        className={cn(
          "text-start",
          uncertain && !corrected && "border-warning focus-visible:ring-warning",
        )}
      />

      {uncertain && !corrected ? (
        <p className="text-xs text-warning">{t("cardScan.lowConfidence")}</p>
      ) : null}
    </div>
  );
}

function SourceMark({ draft, corrected }: { draft: DraftField; corrected: boolean }) {
  const { t } = useTranslation();

  if (corrected) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
        <PencilLine className="size-3.5" />
        {t("cardScan.corrected")}
      </span>
    );
  }
  // "verified" here means a check digit or the two sides agreeing — never that a human checked it.
  if (draft.verified) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-success">
        <CheckCircle2 className="size-3.5" />
        {t("cardScan.crossChecked")}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
      <AlertTriangle className="size-3.5" />
      {t("cardScan.fromOcr", { confidence: draft.confidence })}
    </span>
  );
}
