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
import { useStageCardScanMutation } from "./cardScansApi";
import { useCardReading } from "./useCardReading";
import type { CardScan } from "./types";

// Scan an ID card into a new client (§6.5). The card comes first and the record follows from it:
// capture both sides → the server reads them → check the fields side by side → one confirmation
// creates the client, the case and the filed document.
export function ScanCardPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const currentUser = useAppSelector((s) => s.auth.user);
  const isAdmin = currentUser?.is_admin ?? false;

  const [front, setFront] = useState<CardSide | null>(null);
  const [back, setBack] = useState<CardSide | null>(null);
  const [scanId, setScanId] = useState<number | null>(null);
  const [settled, setSettled] = useState<CardScan | null>(null);

  const [category, setCategory] = useState("");
  const [lawyer, setLawyer] = useState("");

  const { data: categories } = useListCategoriesQuery({});
  const { data: users } = useListUsersQuery({}, { skip: !isAdmin });
  const [stage, { isLoading: staging }] = useStageCardScanMutation();
  const { reading } = useCardReading(scanId, setSettled);

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
    } catch (err) {
      toast.error(apiErrorMessage(err, t("cardScan.uploadError")));
    }
  };

  const restart = () => {
    setScanId(null);
    setSettled(null);
    setFront(null);
    setBack(null);
  };

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
            onConfirmed={(scan) => navigate(scan.document ? "/processes" : "/clients")}
            buildPayload={() => {
              if (isAdmin && !lawyer) {
                toast.error(t("cardScan.pickLawyer"));
                return null;
              }
              return {
                // A lawyer takes their own case; an admin says whose it is.
                assigned_lawyer: isAdmin ? Number(lawyer) : (currentUser?.id ?? null),
                category: category ? Number(category) : null,
              };
            }}
            extra={
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
