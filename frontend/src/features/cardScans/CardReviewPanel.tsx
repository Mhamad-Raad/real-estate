import { AlertTriangle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Maximize2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useAppSelector } from "@/app/hooks";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/lib/toast";
import { fetchBlobUrl } from "@/features/documents/download";
import { apiErrorMessage } from "@/lib/apiError";
import { labeller } from "@/lib/fieldLabels";
import { useFieldErrors } from "@/hooks/useFieldErrors";

import { DraftFieldInput } from "./DraftFieldInput";
import { useConfirmCardScanMutation } from "./cardScansApi";
import { filterPid } from "@/lib/pid";

import { CARD_FIELDS, type CardScan, type ConfirmPayload } from "./types";

type Values = Record<(typeof CARD_FIELDS)[number], string>;

const EMPTY: Values = { full_name: "", pid: "", mother_full_name: "", date_of_birth: "" };

/** The scan on the left, the fields it proposes on the right — check, correct, confirm (§6.4). */
export function CardReviewPanel({
  scan,
  extra,
  onConfirmed,
  buildPayload,
}: {
  scan: CardScan;
  /** Case-level inputs the card cannot supply (phone, address, the spouse block).
   *
   * A **render prop**, not a node: confirming writes those fields too, so the server can reject
   * one — and the error state lives here, with the mutation that produced it. Passed a plain
   * node, they were the only inputs on this screen that could not turn red, which is the exact
   * gap this whole change exists to close.
   */
  extra?: (fieldState: {
    errors: Record<string, string>;
    clear: (field: string) => void;
  }) => React.ReactNode;
  onConfirmed: (scan: CardScan) => void;
  /**
   * Everything beyond the card's own fields — which client, which lawyer, the version lock.
   *
   * Receives the confirmed values so the caller can vet them (the intake form runs the duplicate
   * check on them, §5.7/UC-027), and may be async so that vetting can ask the user. Returning
   * `null` aborts the confirmation.
   */
  buildPayload: (
    values: Values,
  ) => Promise<Omit<ConfirmPayload, keyof Values> | null> | Omit<ConfirmPayload, keyof Values> | null;
}) {
  const { t } = useTranslation();
  const token = useAppSelector((s) => s.auth.access);
  const [confirm, { isLoading }] = useConfirmCardScanMutation();
  const { errors, setFromError, clear } = useFieldErrors();
  const [values, setValues] = useState<Values>(EMPTY);
  const [acknowledged, setAcknowledged] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const fields = scan.draft?.fields ?? {};
  const warnings = scan.draft?.warnings ?? [];

  // Pre-fill from the reading once it arrives; the human edits freely from there.
  useEffect(() => {
    setValues({
      full_name: fields.full_name?.value ?? "",
      pid: fields.pid?.value ?? "",
      mother_full_name: fields.mother_full_name?.value ?? "",
      date_of_birth: fields.date_of_birth?.value ?? "",
    });
    setAcknowledged(false);
    // Re-fill only when a different reading arrives, never on every keystroke.
  }, [scan.id, scan.status]); // eslint-disable-line react-hooks/exhaustive-deps

  // The staged PDF needs the auth header, so a plain <iframe src> would come back 401.
  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    fetchBlobUrl(`/api/v1/card-scans/${scan.id}/file/`, token)
      .then(({ objectUrl: created }) => {
        if (cancelled) {
          URL.revokeObjectURL(created);
          return;
        }
        objectUrl = created;
        setPreviewUrl(created);
      })
      .catch(() => toast.error(t("cardScan.previewError")));

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl); // never leak the blob
    };
  }, [scan.id, token, t]);

  const complete = useMemo(
    () => CARD_FIELDS.every((name) => values[name].trim().length > 0),
    [values],
  );

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const rest = await buildPayload(values);
    if (!rest) return;
    try {
      const confirmed = await confirm({
        id: scan.id,
        ...values,
        date_of_birth: values.date_of_birth || null,
        ...rest,
      }).unwrap();
      toast.success(t("cardScan.confirmed"));
      onConfirmed(confirmed);
    } catch (err) {
      // Confirming creates the client, the case and the filed document in one transaction (§6.5),
      // so a single bad field loses the whole act — the lawyer has to be told which one.
      setFromError(err);
      toast.error(apiErrorMessage(err, t("cardScan.confirmError"), labeller(t), t));
    }
  };

  return (
    <form onSubmit={submit} className="grid gap-6 lg:grid-cols-2">
      {/* Left: the card itself. Sticky, because the fields pane is now the longer of the two and
          the whole point is comparing them — a scan that scrolls out of view cannot be compared.
          This image is also the archived government record, so it has to be judged for legibility
          and not merely read: "open full size" exists for that (UC-029). */}
      <div className="space-y-2 lg:sticky lg:top-4 lg:self-start">
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs text-muted-foreground">{t("cardScan.scannedCard")}</p>
          {previewUrl && (
            <a
              href={previewUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
            >
              <Maximize2 className="size-3.5" />
              {t("cardScan.openFullSize")}
            </a>
          )}
        </div>
        {previewUrl ? (
          <iframe
            src={previewUrl}
            title={t("cardScan.scannedCard")}
            className="h-[36rem] w-full rounded-md border border-border bg-white"
          />
        ) : (
          <div className="flex h-[36rem] items-center justify-center rounded-md border border-border">
            <Spinner />
          </div>
        )}
        <p className="text-xs text-muted-foreground">{t("cardScan.qualityHint")}</p>
      </div>

      {/* Right: what it says, editable. */}
      <div className="space-y-4">
        {scan.status === "failed" ? (
          <Notice title={t("cardScan.readingFailedTitle")}>
            {t("cardScan.readingFailedBody")}
          </Notice>
        ) : null}

        {warnings.map((warning) => (
          <Notice key={warning}>
            {warning}
          </Notice>
        ))}

        {CARD_FIELDS.map((name) => (
          <DraftFieldInput
            key={name}
            name={name}
            label={t(`cardScan.field.${name}`)}
            value={values[name]}
            draft={fields[name]}
            type={name === "date_of_birth" ? "date" : "text"}
            required
            error={errors[name]}
            onChange={(value) => {
              clear(name);
              // The card's own number is a national ID like any other, and this is where a lawyer
              // corrects what the OCR proposed — so it filters exactly as the intake box does.
              const next = name === "pid" ? filterPid(value) : value;
              setValues((current) => ({ ...current, [name]: next }));
            }}
          />
        ))}

        {extra?.({ errors, clear })}

        {/* §6.4: the match warning must be acknowledged before anything is written. */}
        <label className="flex items-start gap-2 rounded-md border border-border bg-muted/40 p-3 text-sm">
          <Checkbox
            checked={acknowledged}
            onChange={(e) => setAcknowledged(e.target.checked)}
            className="mt-0.5"
          />
          <span>{t("cardScan.matchWarning")}</span>
        </label>

        <Button type="submit" disabled={!acknowledged || !complete || isLoading} className="w-full">
          {isLoading ? <Spinner /> : null}
          {t("cardScan.confirmAndSave")}
        </Button>
        {!complete ? (
          <p className="text-xs text-muted-foreground">{t("cardScan.fillEveryField")}</p>
        ) : null}
      </div>
    </form>
  );
}

/** Everything a reading has to say for itself is a caution, so there is only one tone. */
function Notice({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-2 rounded-md border border-warning/40 bg-warning/10 p-3 text-sm">
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" />
      <div>
        {title ? <p className="font-medium">{title}</p> : null}
        <p className="text-muted-foreground">{children}</p>
      </div>
    </div>
  );
}
