import { ScanLine } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toaster";
import { apiErrorMessage } from "@/lib/apiError";

import { CardCapture, type CardSide } from "./CardCapture";
import { CardReviewPanel } from "./CardReviewPanel";
import { SpouseSection } from "./SpouseSection";
import { EMPTY_SPOUSE, SPOUSE_FIELDS, type SpouseValues } from "./spouseFields";
import { useConfirmCardScanMutation, useStageCardScanMutation } from "./cardScansApi";
import { useCardReading } from "./useCardReading";
import type { CardScan } from "./types";

// The scan branch of the Step-1 intake form (§6.5, UC-024). The card comes first and the record
// follows from it: capture both sides → the server reads them → check the fields side by side →
// one confirmation creates the beneficiary, the case and the filed document. A married beneficiary
// brings their spouse's card too, because the eligibility letter prints a spouse row (§6.6).
//
// The case fields (category, land, assignee) are owned by the parent form, so they are asked once
// no matter which way the beneficiary is being created.
export function ScanIntakePanel({
  category,
  assignedLawyer,
  landId,
  landAddress,
  onCreated,
  onBeforeCreate,
}: {
  category: number | null;
  assignedLawyer: number | null;
  landId: string;
  landAddress: string;
  onCreated: (confirmed: CardScan) => void;
  /**
   * Vets the beneficiary about to be created — the intake form runs the duplicate check here
   * (§5.7, UC-027). Resolving `false` aborts, so a hard match never reaches the server.
   */
  onBeforeCreate?: (candidate: { pid: string; mother_full_name: string; spouse_pid: string }) => Promise<boolean>;
}) {
  const { t } = useTranslation();

  const [front, setFront] = useState<CardSide | null>(null);
  const [back, setBack] = useState<CardSide | null>(null);
  const [spouseFront, setSpouseFront] = useState<CardSide | null>(null);
  const [spouseBack, setSpouseBack] = useState<CardSide | null>(null);

  const [scanId, setScanId] = useState<number | null>(null);
  const [settled, setSettled] = useState<CardScan | null>(null);
  const [spouseScanId, setSpouseScanId] = useState<number | null>(null);
  const [spouseSettled, setSpouseSettled] = useState<CardScan | null>(null);

  const [married, setMarried] = useState(false);
  const [spouse, setSpouse] = useState<SpouseValues>(EMPTY_SPOUSE);

  const [stage, { isLoading: staging }] = useStageCardScanMutation();
  const [confirmSpouse] = useConfirmCardScanMutation();
  const { reading } = useCardReading(scanId, setSettled);
  const { reading: readingSpouse } = useCardReading(spouseScanId, onSpouseRead);

  // Pre-fill the spouse form from its own reading, leaving anything already typed alone.
  function onSpouseRead(scan: CardScan) {
    setSpouseSettled(scan);
    const fields = scan.draft?.fields ?? {};
    setSpouse((current) => {
      const next = { ...current };
      for (const { name, from } of SPOUSE_FIELDS) {
        if (!next[name]) next[name] = fields[from]?.value ?? "";
      }
      return next;
    });
  }

  const send = async () => {
    if (!front) return;
    try {
      const scan = await stage({
        document_type: "ClientID",
        front: front.file,
        back: back?.file ?? null,
      }).unwrap();
      setSettled(null);
      setScanId(scan.id);

      if (married && spouseFront) {
        const spouseScan = await stage({
          document_type: "SpouseID",
          front: spouseFront.file,
          back: spouseBack?.file ?? null,
        }).unwrap();
        setSpouseSettled(null);
        setSpouseScanId(spouseScan.id);
      }
    } catch (err) {
      toast.error(apiErrorMessage(err, t("cardScan.uploadError")));
    }
  };

  // The beneficiary's card creates the record; the spouse's card is then filed onto it. Two
  // calls, because the client has to exist before its spouse's document can belong anywhere.
  const fileSpouseCard = async (confirmed: CardScan) => {
    if (!spouseScanId || confirmed.client == null) return;
    try {
      await confirmSpouse({
        id: spouseScanId,
        client: confirmed.client,
        client_version: confirmed.client_version ?? undefined,
        full_name: spouse.spouse_name,
        pid: spouse.spouse_pid,
        mother_full_name: spouse.spouse_mother_full_name,
        date_of_birth: spouse.spouse_date_of_birth || null,
      }).unwrap();
    } catch (err) {
      // The beneficiary is already saved, so this must not read as a total failure — Step 1 will
      // show the spouse ID still missing and the scan is still staged to retry.
      toast.error(apiErrorMessage(err, t("cardScan.spouseFileError")));
    }
  };

  const restart = () => {
    setScanId(null);
    setSettled(null);
    setSpouseScanId(null);
    setSpouseSettled(null);
    setFront(null);
    setBack(null);
    setSpouseFront(null);
    setSpouseBack(null);
    setSpouse(EMPTY_SPOUSE);
  };

  const spouseComplete =
    !married ||
    (spouse.spouse_name.trim() &&
      spouse.spouse_mother_full_name.trim() &&
      spouse.spouse_date_of_birth.trim());

  if (settled) {
    return (
      <div className="space-y-4">
        <CardReviewPanel
          scan={settled}
          onConfirmed={async (confirmed) => {
            if (married) await fileSpouseCard(confirmed);
            onCreated(confirmed);
          }}
          buildPayload={async (values) => {
            if (assignedLawyer == null) {
              toast.error(t("cardScan.pickLawyer"));
              return null;
            }
            if (!spouseComplete) {
              toast.error(t("cardScan.spouseIncomplete"));
              return null;
            }
            // The card creates the person, so the duplicate check belongs here — this is the
            // branch the office actually uses, and the one that had no check at all (UC-027).
            if (onBeforeCreate) {
              const clear = await onBeforeCreate({
                pid: values.pid,
                mother_full_name: values.mother_full_name,
                spouse_pid: married ? spouse.spouse_pid : "",
              });
              if (!clear) return null;
            }
            return {
              assigned_lawyer: assignedLawyer,
              category,
              land_id: landId,
              land_address: landAddress,
              marital_status: married ? "married" : "single",
              ...(married
                ? {
                    spouse_name: spouse.spouse_name,
                    spouse_mother_full_name: spouse.spouse_mother_full_name,
                    spouse_date_of_birth: spouse.spouse_date_of_birth || null,
                    spouse_pid: spouse.spouse_pid,
                  }
                : {}),
            };
          }}
          extra={
            married ? (
              <SpouseSection
                scan={spouseSettled}
                reading={readingSpouse}
                values={spouse}
                onChange={setSpouse}
              />
            ) : null
          }
        />
        <Button type="button" variant="ghost" size="sm" onClick={restart}>
          {t("cardScan.startOver")}
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-6 md:grid-cols-2">
        <CardCapture
          label={t("cardScan.front")}
          hint={t("cardScan.frontHint")}
          side={front}
          onChange={setFront}
          disabled={staging || reading}
        />
        <CardCapture
          label={t("cardScan.back")}
          hint={t("cardScan.backHint")}
          side={back}
          onChange={setBack}
          disabled={staging || reading}
        />
      </div>

      <label className="flex items-start gap-2 rounded-md border border-border bg-muted/40 p-3 text-sm">
        <Checkbox
          checked={married}
          onChange={(e) => setMarried(e.target.checked)}
          className="mt-0.5"
        />
        <span>
          {t("cardScan.married")}
          <span className="block text-xs text-muted-foreground">
            {t("cardScan.marriedHint")}
          </span>
        </span>
      </label>

      {married ? (
        <div className="grid gap-6 md:grid-cols-2">
          <CardCapture
            label={t("cardScan.spouseFront")}
            hint={t("cardScan.frontHint")}
            side={spouseFront}
            onChange={setSpouseFront}
            disabled={staging || reading}
          />
          <CardCapture
            label={t("cardScan.spouseBack")}
            hint={t("cardScan.backHint")}
            side={spouseBack}
            onChange={setSpouseBack}
            disabled={staging || reading}
          />
        </div>
      ) : null}

      <div className="flex items-center gap-3">
        <Button type="button" onClick={send} disabled={!front || staging || reading}>
          {staging || reading ? <Spinner /> : <ScanLine className="size-4" />}
          {reading ? t("cardScan.reading") : t("cardScan.read")}
        </Button>
        {!back && front ? (
          <p className="text-xs text-muted-foreground">{t("cardScan.noBackNote")}</p>
        ) : null}
      </div>
    </div>
  );
}
