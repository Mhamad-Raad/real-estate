import { ArrowLeft, PenLine, ScanLine } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { useAppSelector } from "@/app/hooks";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { FormSection } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toaster";
import { ScanIntakePanel } from "@/features/cardScans/ScanIntakePanel";
import { useListCategoriesQuery } from "@/features/categories/categoriesApi";
import { ClientFields } from "@/features/clients/ClientFields";
import { DuplicateWarningDialog } from "@/features/clients/DuplicateWarningDialog";
import { EMPTY_CLIENT, type ClientDraft } from "@/features/clients/clientForm";
import { useCheckDuplicateMutation } from "@/features/clients/clientsApi";
import type { DuplicateCheckResult } from "@/features/clients/types";
import { useListLawyersQuery } from "@/features/users/lawyersApi";
import { apiErrorMessage, apiErrorStatus } from "@/lib/apiError";

import { useCreateProcessMutation } from "./processesApi";

type Mode = "scan" | "manual";

// Opening a case IS Step 1 (§5, UC-024): the beneficiary is created here — from their ID card, from
// the register, or by hand — alongside the land and category, and nothing is written until the one
// submit at the bottom. An abandoned form therefore leaves nothing behind, which matters because
// nothing in this system is ever hard-deleted (§11.1).
export function ProcessCreatePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const currentUser = useAppSelector((s) => s.auth.user);
  const isAdmin = currentUser?.is_admin ?? false;

  const [mode, setMode] = useState<Mode>("scan");
  const [category, setCategory] = useState("");
  const [landId, setLandId] = useState("");
  const [landAddress, setLandAddress] = useState("");
  const [lawyer, setLawyer] = useState("");

  const [draft, setDraft] = useState<ClientDraft>(EMPTY_CLIENT);

  const { data: categories } = useListCategoriesQuery();
  // `/lawyers/`, not the paginated `/users/`: that one stops at 25 and lists people who have left.
  const { data: lawyers } = useListLawyersQuery(undefined, { skip: !isAdmin });
  const [create, { isLoading }] = useCreateProcessMutation();
  const [checkDuplicate] = useCheckDuplicateMutation();

  // §5.7's pre-save duplicate check. It lives here because this is now the only screen that can
  // create a beneficiary (UC-026), and it serves BOTH branches that do so — typed and scanned.
  const [warning, setWarning] = useState<DuplicateCheckResult | null>(null);
  // The dialog is the answer to an async question, so the guard parks on a promise the buttons
  // resolve. Held in a ref: a re-render must not lose the pending decision.
  const decision = useRef<((proceed: boolean) => void) | null>(null);

  /** `true` when it is safe to create. A hard match can only ever be cancelled (§5.7). */
  const guardDuplicates = async (candidate: {
    pid: string;
    mother_full_name: string;
    spouse_pid: string;
  }) => {
    try {
      const result = await checkDuplicate(candidate).unwrap();
      const hit =
        result.pid_matches.length ||
        result.household_matches.length ||
        result.mother_name_matches.length;
      if (!hit) return true;
      setWarning(result);
      return await new Promise<boolean>((resolve) => {
        decision.current = resolve;
      });
    } catch {
      // A failed check must not silently wave a possible duplicate through.
      toast.error(t("common.loadError"));
      return false;
    }
  };

  const settle = (proceed: boolean) => {
    decision.current?.(proceed);
    decision.current = null;
    setWarning(null);
  };

  // A lawyer always takes their own case; an admin says whose it is (mirrored server-side, §7.2).
  const assignedLawyer = isAdmin ? (lawyer ? Number(lawyer) : null) : (currentUser?.id ?? null);

  // Switching how the beneficiary is identified must not carry the other mode's half-entry along.
  useEffect(() => {
    setDraft(EMPTY_CLIENT);
  }, [mode]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isAdmin && !lawyer) {
      toast.error(t("processes.pickLawyer"));
      return;
    }
    {
      const clear = await guardDuplicates({
        pid: draft.pid,
        mother_full_name: draft.mother_full_name,
        spouse_pid: draft.marital_status === "married" ? draft.spouse_pid : "",
      });
      if (!clear) return;
    }
    try {
      const process = await create({
        client_data: { ...draft, category: category ? Number(category) : null },
        category: category ? Number(category) : null,
        land_id: landId,
        land_address: landAddress,
        ...(assignedLawyer ? { assigned_lawyer: assignedLawyer } : {}),
      }).unwrap();
      toast.success(t("processes.created"));
      // Straight into the case — the lawyer's next act is always the rest of Step 1.
      navigate(`/processes/${process.id}`);
    } catch (err) {
      toast.error(
        apiErrorStatus(err) === 409
          ? t("processes.duplicateAllocation")
          : apiErrorMessage(err, t("common.saveError")),
      );
    }
  };

  // Two ways to name the beneficiary. There is deliberately no "pick an existing client":
  // one person holds one live allocation (§3.7), so an existing client already has a case.
  // Re-application after a rejection is offered on the rejected case itself (UC-028).
  const MODES: { key: Mode; icon: typeof ScanLine; label: string; hint: string }[] = [
    { key: "scan", icon: ScanLine, label: t("intake.modeScan"), hint: t("intake.modeScanHint") },
    { key: "manual", icon: PenLine, label: t("intake.modeManual"), hint: t("intake.modeManualHint") },
  ];

  const caseFields = (
    <div className="grid gap-4 sm:grid-cols-2">
      <div className="space-y-1.5">
        <Label htmlFor="i-category">{t("processes.category")}</Label>
        <Select id="i-category" value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">{t("common.none")}</option>
          {(categories ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {c.code} — {c.name}
            </option>
          ))}
        </Select>
      </div>
      {isAdmin && (
        <div className="space-y-1.5">
          <Label htmlFor="i-lawyer">{t("processes.assignedLawyer")}</Label>
          <Select id="i-lawyer" value={lawyer} onChange={(e) => setLawyer(e.target.value)}>
            <option value="">{t("cardScan.selectLawyer")}</option>
            {(lawyers ?? []).map((l) => (
              <option key={l.id} value={l.id}>
                {l.username}
              </option>
            ))}
          </Select>
        </div>
      )}
      <div className="space-y-1.5">
        <Label htmlFor="i-landid">{t("workflow.landId")}</Label>
        <Input
          id="i-landid"
          value={landId}
          onChange={(e) => setLandId(e.target.value)}
          placeholder={t("workflow.landIdPlaceholder")}
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="i-address">{t("workflow.landAddress")}</Label>
        <Input
          id="i-address"
          value={landAddress}
          onChange={(e) => setLandAddress(e.target.value)}
          placeholder={t("workflow.landAddressPlaceholder")}
        />
      </div>
    </div>
  );

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{t("intake.title")}</h1>
          <p className="text-sm text-muted-foreground">{t("intake.subtitle")}</p>
        </div>
        <Button type="button" variant="ghost" onClick={() => navigate("/processes")}>
          <ArrowLeft className="size-4 rtl:rotate-180" />
          {t("intake.back")}
        </Button>
      </div>

      <FormSection title={t("intake.beneficiary")} description={t("intake.beneficiaryHint")}>
        <div className="grid gap-3 sm:grid-cols-2">
          {MODES.map(({ key, icon: Icon, label, hint }) => (
            <button
              key={key}
              type="button"
              aria-pressed={mode === key}
              onClick={() => setMode(key)}
              className={
                "flex flex-col items-start gap-1 rounded-md border p-3 text-start transition-colors " +
                (mode === key
                  ? "border-primary bg-primary/5"
                  : "border-border hover:bg-accent/50")
              }
            >
              <span className="flex items-center gap-2 text-sm font-medium">
                <Icon className="size-4" />
                {label}
              </span>
              <span className="text-xs text-muted-foreground">{hint}</span>
            </button>
          ))}
        </div>

        {mode === "manual" && <ClientFields value={draft} onChange={setDraft} />}
      </FormSection>

      <FormSection title={t("intake.caseDetails")} description={t("intake.caseDetailsHint")}>
        {caseFields}
      </FormSection>

      {mode === "scan" ? (
        <FormSection title={t("intake.idCard")} description={t("intake.idCardHint")}>
          <ScanIntakePanel
            category={category ? Number(category) : null}
            assignedLawyer={assignedLawyer}
            landId={landId}
            landAddress={landAddress}
            onBeforeCreate={guardDuplicates}
            onCreated={(confirmed) =>
              confirmed.process
                ? navigate(`/processes/${confirmed.process}`)
                : navigate("/processes")
            }
          />
        </FormSection>
      ) : (
        <form onSubmit={submit} className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={() => navigate("/processes")}>
            {t("common.cancel")}
          </Button>
          <Button
            type="submit"
            disabled={isLoading || !draft.pid.trim()}
          >
            {isLoading && <Spinner />}
            {t("intake.create")}
          </Button>
        </form>
      )}

      <DuplicateWarningDialog
        open={Boolean(warning)}
        result={warning}
        onProceed={() => settle(true)}
        onClose={() => settle(false)}
      />
    </div>
  );
}
