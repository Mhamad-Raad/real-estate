import { ScanLine } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toaster";
import { apiErrorMessage } from "@/lib/apiError";

import { CardCapture, type CardSide } from "./CardCapture";
import { SpouseSection } from "./SpouseSection";
import { EMPTY_SPOUSE, SPOUSE_FIELDS, type SpouseValues } from "./spouseFields";
import { useConfirmCardScanMutation, useStageCardScanMutation } from "./cardScansApi";
import { useCardReading } from "./useCardReading";
import type { CardScan } from "./types";

/**
 * Read a spouse's ID card onto a case that already exists (UC-048).
 *
 * The intake form could always do this, but only while creating the beneficiary — so a couple who
 * married after the case opened, or a case typed in by hand, had no way to read the card at all
 * and the details were re-keyed from paper. The server side needed nothing: `confirm_scan` already
 * files a spouse card against an existing client; there was simply no screen calling it that way
 * once the standalone scan page was removed (UC-024).
 */
export function SpouseCardPanel({
  clientId,
  clientVersion,
  canEdit,
}: {
  clientId: number;
  clientVersion: number;
  canEdit: boolean;
}) {
  const { t } = useTranslation();
  const [front, setFront] = useState<CardSide | null>(null);
  const [back, setBack] = useState<CardSide | null>(null);
  const [scanId, setScanId] = useState<number | null>(null);
  const [values, setValues] = useState<SpouseValues>(EMPTY_SPOUSE);

  const [stage, { isLoading: staging }] = useStageCardScanMutation();
  const [confirm, { isLoading: confirming }] = useConfirmCardScanMutation();

  // A reading only ever *proposes*: whatever the engine returns fills the blanks, and a value the
  // lawyer has already corrected is left alone (§6.5).
  const { scan, reading } = useCardReading(scanId, (settled: CardScan) => {
    const fields = settled.draft?.fields ?? {};
    setValues((current) => {
      const next = { ...current };
      for (const { name, from } of SPOUSE_FIELDS) {
        if (!next[name]) next[name] = fields[from]?.value ?? "";
      }
      return next;
    });
  });

  const send = async () => {
    if (!front) return;
    try {
      const staged = await stage({
        document_type: "SpouseID",
        front: front.file,
        back: back?.file ?? null,
      }).unwrap();
      setScanId(staged.id);
    } catch (err) {
      toast.error(apiErrorMessage(err, t("cardScan.uploadError")));
    }
  };

  const file = async () => {
    if (!scanId) return;
    try {
      await confirm({
        id: scanId,
        client: clientId,
        client_version: clientVersion,
        full_name: values.spouse_name,
        pid: values.spouse_pid,
        mother_full_name: values.spouse_mother_full_name,
        date_of_birth: values.spouse_date_of_birth || null,
      }).unwrap();
      toast.success(t("cardScan.spouseFiled"));
      setScanId(null);
      setFront(null);
      setBack(null);
      setValues(EMPTY_SPOUSE);
    } catch (err) {
      toast.error(apiErrorMessage(err, t("cardScan.spouseFileError")));
    }
  };

  if (!canEdit) return null;

  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">{t("cardScan.spouseAfterHint")}</p>

      {scanId === null ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            <CardCapture label={t("cardScan.spouseFront")} side={front} onChange={setFront} />
            <CardCapture label={t("cardScan.spouseBack")} side={back} onChange={setBack} />
          </div>
          <Button size="sm" onClick={send} disabled={!front || staging}>
            {staging ? <Spinner /> : <ScanLine className="size-4" />}
            {t("cardScan.read")}
          </Button>
        </>
      ) : (
        <>
          <SpouseSection scan={scan ?? null} reading={reading} values={values} onChange={setValues} />
          <div className="flex gap-2">
            <Button size="sm" onClick={file} disabled={confirming || reading}>
              {confirming && <Spinner />}
              {t("cardScan.confirmSpouse")}
            </Button>
            <Button size="sm" variant="outline" onClick={() => setScanId(null)} disabled={confirming}>
              {t("common.cancel")}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
