import { ArrowLeft, PenLine, ScanLine } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { useAppSelector } from "@/app/hooks";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { FormSection } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/lib/toast";
import { ScanIntakePanel } from "@/features/cardScans/ScanIntakePanel";
import { useListCategoriesQuery } from "@/features/categories/categoriesApi";
import { ClientFields } from "@/features/clients/ClientFields";
import { EMPTY_CLIENT, type ClientDraft } from "@/features/clients/clientForm";
import { useDuplicateGate } from "@/features/clients/useDuplicateGate";
import { useListLawyersQuery } from "@/features/users/lawyersApi";
import { apiErrorMessage, apiErrorStatus } from "@/lib/apiError";
import { labeller } from "@/lib/fieldLabels";
import { useFieldErrors } from "@/hooks/useFieldErrors";
import { FieldError } from "@/components/ui/field-error";

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
  // Whoever opens the case owns it unless the admin says otherwise (UC-092). A lawyer never
  // sees this field and is assigned server-side; only an admin had to pick from an empty box.
  const [lawyer, setLawyer] = useState(() => (currentUser?.id ? String(currentUser.id) : ""));

  const [draft, setDraft] = useState<ClientDraft>(EMPTY_CLIENT);
  const { errors, setErrors, setFromError, clear } = useFieldErrors();

  const { data: categories } = useListCategoriesQuery();
  // `/lawyers/`, not the paginated `/users/`: that one stops at 25 and lists people who have left.
  const { data: lawyers } = useListLawyersQuery(undefined, { skip: !isAdmin });
  const [create, { isLoading }] = useCreateProcessMutation();

  // §5.7's pre-save duplicate check, shared with the backlog form (§5.9) so the two doors cannot
  // ask different questions — see `useDuplicateGate`.
  const { guard, dialog: duplicateDialog } = useDuplicateGate();

  /** `true` when it is safe to create. A hard match can only ever be cancelled (§5.7).
   *
   * Both branches vet through here — typed and scanned — so the category check belongs here too
   * rather than in the manual submit alone. It is required because the unique code takes its first
   * letter from the category and the category can never be set afterwards (UC-056, UC-059).
   */
  const guardDuplicates = async (candidate: {
    pid: string;
    mother_full_name: string;
    spouse_pid: string;
  }) => {
    if (!category) {
      // Marked as well as announced: a client-side refusal has to point at the same control a
      // server-side one would, or the user learns to trust the red border only half the time.
      setErrors({ category: t("processes.pickCategory") });
      toast.error(t("processes.pickCategory"));
      return false;
    }
    return guard(candidate);
  };

  // A lawyer always takes their own case; an admin says whose it is (mirrored server-side, §7.2).
  const assignedLawyer = isAdmin ? (lawyer ? Number(lawyer) : null) : (currentUser?.id ?? null);

  // **Switching modes deliberately keeps what has been typed (UC-089).** This used to blank the
  // draft and the errors, on the reasoning that one mode must not carry the other's half-entry
  // along — but the scan branch never reads `draft` (it builds its payload from the confirmed
  // card), so nothing was ever carried anywhere. All the reset did was destroy a filled-in form
  // for anyone who looked at the other tab and came back. The errors stay for the same reason:
  // `category` and `assigned_lawyer` are **case** fields, shown in both modes, so clearing them
  // threw away a warning that still applied.

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isAdmin && !lawyer) {
      setErrors({ assigned_lawyer: t("processes.pickLawyer") });
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
        // One value, sent to both: the beneficiary's category and the case's are the same thing.
        client_data: { ...draft, category: Number(category) },
        category: Number(category),
        land_id: landId,
        land_address: landAddress,
        ...(assignedLawyer ? { assigned_lawyer: assignedLawyer } : {}),
      }).unwrap();
      toast.success(t("processes.created"));
      // Straight into the case — the lawyer's next act is always the rest of Step 1.
      navigate(`/processes/${process.id}`);
    } catch (err) {
      // Mark every field the server named, so the offending input is red rather than the user
      // re-reading the whole form. The toast carries the first one, named.
      setFromError(err);
      toast.error(
        apiErrorStatus(err) === 409
          ? t("processes.duplicateAllocation")
          : apiErrorMessage(err, t("common.saveError"), labeller(t), t),
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
        <Select
          id="i-category"
          value={category}
          onChange={(e) => {
            clear("category");
            setCategory(e.target.value);
          }}
          invalid={Boolean(errors.category)}
        >
          <option value="">{t("processes.chooseCategory")}</option>
          {(categories ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {c.code} — {c.name}
            </option>
          ))}
        </Select>
        <FieldError message={errors.category} />
      </div>
      {isAdmin && (
        <div className="space-y-1.5">
          <Label htmlFor="i-lawyer">{t("processes.assignedLawyer")}</Label>
          <Select
            id="i-lawyer"
            value={lawyer}
            onChange={(e) => {
              clear("assigned_lawyer");
              setLawyer(e.target.value);
            }}
            invalid={Boolean(errors.assigned_lawyer)}
          >
            <option value="">{t("cardScan.selectLawyer")}</option>
            {(lawyers ?? []).map((l) => (
              <option key={l.id} value={l.id}>
                {l.username}
              </option>
            ))}
          </Select>
          <FieldError message={errors.assigned_lawyer} />
        </div>
      )}
      <div className="space-y-1.5">
        <Label htmlFor="i-landid">{t("workflow.landId")}</Label>
        <Input
          id="i-landid"
          value={landId}
          onChange={(e) => {
            clear("land_id");
            setLandId(e.target.value);
          }}
          placeholder={t("workflow.landIdPlaceholder")}
          invalid={Boolean(errors.land_id)}
        />
        <FieldError message={errors.land_id} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="i-address">{t("workflow.landAddress")}</Label>
        <Input
          id="i-address"
          value={landAddress}
          onChange={(e) => {
            clear("land_address");
            setLandAddress(e.target.value);
          }}
          placeholder={t("workflow.landAddressPlaceholder")}
          invalid={Boolean(errors.land_address)}
        />
        <FieldError message={errors.land_address} />
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

        {/* `showCategory={false}`: the case's category is asked once in the case section below.
            A second picker here looked editable but was discarded — `submit` overwrites
            `client_data.category` with the case-level one. */}
        {mode === "manual" && (
          <ClientFields
            value={draft}
            onChange={setDraft}
            showCategory={false}
            errors={errors}
            onFieldEdit={clear}
          />
        )}
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

      {duplicateDialog}
    </div>
  );
}
