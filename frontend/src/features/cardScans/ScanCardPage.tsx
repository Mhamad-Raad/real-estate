import { ArrowLeft, ScanLine } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { useAppSelector } from "@/app/hooks";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toaster";
import { useListCategoriesQuery } from "@/features/categories/categoriesApi";
import { useListUsersQuery } from "@/features/users/usersApi";
import { apiErrorMessage } from "@/lib/apiError";

import { CardCapture, type CardSide } from "./CardCapture";
import { CardReviewPanel } from "./CardReviewPanel";
import { SpouseSection } from "./SpouseSection";
import { EMPTY_SPOUSE, SPOUSE_FIELDS, type SpouseValues } from "./spouseFields";
import { useConfirmCardScanMutation, useStageCardScanMutation } from "./cardScansApi";
import { useCardReading } from "./useCardReading";
import type { CardScan } from "./types";

// Scan an ID card into a new beneficiary (§6.5). The card comes first and the record follows from
// it: capture both sides → the server reads them → check the fields side by side → one
// confirmation creates the beneficiary, the case and the filed document. A married beneficiary
// brings their spouse's card too, because the eligibility letter prints a spouse row (§6.6).
export function ScanCardPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const currentUser = useAppSelector((s) => s.auth.user);
  const isAdmin = currentUser?.is_admin ?? false;

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
  const [category, setCategory] = useState("");
  const [lawyer, setLawyer] = useState("");

  const { data: categories } = useListCategoriesQuery({});
  const { data: users } = useListUsersQuery({}, { skip: !isAdmin });
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

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold">
            <ScanLine className="size-6" />
            {t("cardScan.title")}
          </h1>
          <p className="text-sm text-muted-foreground">{t("cardScan.subtitle")}</p>
        </div>
        <Button type="button" variant="ghost" onClick={() => navigate("/clients")}>
          <ArrowLeft className="size-4 rtl:rotate-180" />
          {t("cardScan.backToClients")}
        </Button>
      </div>

      {settled ? (
        <>
          <CardReviewPanel
            scan={settled}
            onConfirmed={async (confirmed) => {
              if (married) await fileSpouseCard(confirmed);
              navigate("/processes");
            }}
            buildPayload={() => {
              if (isAdmin && !lawyer) {
                toast.error(t("cardScan.pickLawyer"));
                return null;
              }
              if (!spouseComplete) {
                toast.error(t("cardScan.spouseIncomplete"));
                return null;
              }
              return {
                // A lawyer takes their own case; an admin says whose it is.
                assigned_lawyer: isAdmin ? Number(lawyer) : (currentUser?.id ?? null),
                category: category ? Number(category) : null,
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
              <div className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label htmlFor="scan-category">{t("clients.category")}</Label>
                    <Select
                      id="scan-category"
                      value={category}
                      onChange={(e) => setCategory(e.target.value)}
                    >
                      <option value="">{t("common.none")}</option>
                      {categories?.results.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.code} — {item.name}
                        </option>
                      ))}
                    </Select>
                  </div>
                  {isAdmin ? (
                    <div className="space-y-1.5">
                      <Label htmlFor="scan-lawyer">{t("processes.assignedLawyer")}</Label>
                      <Select
                        id="scan-lawyer"
                        value={lawyer}
                        onChange={(e) => setLawyer(e.target.value)}
                      >
                        <option value="">{t("cardScan.selectLawyer")}</option>
                        {users?.results.map((user) => (
                          <option key={user.id} value={user.id}>
                            {user.username}
                          </option>
                        ))}
                      </Select>
                    </div>
                  ) : null}
                </div>

                {married ? (
                  <SpouseSection
                    scan={spouseSettled}
                    reading={readingSpouse}
                    values={spouse}
                    onChange={setSpouse}
                  />
                ) : null}
              </div>
            }
          />
          <Button type="button" variant="ghost" size="sm" onClick={restart}>
            {t("cardScan.startOver")}
          </Button>
        </>
      ) : (
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
            <input
              type="checkbox"
              checked={married}
              onChange={(e) => setMarried(e.target.checked)}
              className="mt-0.5 size-4 shrink-0"
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
      )}
    </div>
  );
}
