import { ArrowLeft, PenLine, ScanLine, UserSearch } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { useAppSelector } from "@/app/hooks";
import { Button } from "@/components/ui/button";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { FormSection } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toaster";
import { ScanIntakePanel } from "@/features/cardScans/ScanIntakePanel";
import { useListCategoriesQuery } from "@/features/categories/categoriesApi";
import { ClientFields } from "@/features/clients/ClientFields";
import { EMPTY_CLIENT, type ClientDraft } from "@/features/clients/clientForm";
import { useListClientsQuery } from "@/features/clients/clientsApi";
import { useListUsersQuery } from "@/features/users/usersApi";
import { useDebounced } from "@/hooks/useDebounced";
import { apiErrorMessage, apiErrorStatus } from "@/lib/apiError";

import { useCreateProcessMutation } from "./processesApi";

type Mode = "scan" | "existing" | "manual";

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

  const [clientId, setClientId] = useState("");
  const [clientTerm, setClientTerm] = useState("");
  const clientSearch = useDebounced(clientTerm, 300);
  const [draft, setDraft] = useState<ClientDraft>(EMPTY_CLIENT);

  const { data: categories } = useListCategoriesQuery({});
  const { data: users } = useListUsersQuery({}, { skip: !isAdmin });
  const { data: clients, isFetching: searching } = useListClientsQuery(
    { search: clientSearch },
    { skip: mode !== "existing" },
  );
  const [create, { isLoading }] = useCreateProcessMutation();

  // A lawyer always takes their own case; an admin says whose it is (mirrored server-side, §7.2).
  const assignedLawyer = isAdmin ? (lawyer ? Number(lawyer) : null) : (currentUser?.id ?? null);

  // Switching how the beneficiary is identified must not carry the other mode's half-entry along.
  useEffect(() => {
    setClientId("");
    setClientTerm("");
    setDraft(EMPTY_CLIENT);
  }, [mode]);

  const options: ComboboxOption[] = (clients?.results ?? []).map((c) => ({
    value: String(c.id),
    label: c.full_name,
    hint: c.pid,
  }));
  // The list is one page deep, so a truncated result must say so rather than look complete (UC-023).
  const total = clients?.count ?? 0;
  const truncated = total > options.length;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isAdmin && !lawyer) {
      toast.error(t("processes.pickLawyer"));
      return;
    }
    try {
      const process = await create({
        ...(mode === "existing"
          ? { client: Number(clientId) }
          : { client_data: { ...draft, category: category ? Number(category) : null } }),
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

  const MODES: { key: Mode; icon: typeof ScanLine; label: string; hint: string }[] = [
    { key: "scan", icon: ScanLine, label: t("intake.modeScan"), hint: t("intake.modeScanHint") },
    { key: "existing", icon: UserSearch, label: t("intake.modeExisting"), hint: t("intake.modeExistingHint") },
    { key: "manual", icon: PenLine, label: t("intake.modeManual"), hint: t("intake.modeManualHint") },
  ];

  const caseFields = (
    <div className="grid gap-4 sm:grid-cols-2">
      <div className="space-y-1.5">
        <Label htmlFor="i-category">{t("processes.category")}</Label>
        <Select id="i-category" value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">{t("common.none")}</option>
          {(categories?.results ?? []).map((c) => (
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
            {(users?.results ?? []).map((u) => (
              <option key={u.id} value={u.id}>
                {u.username}
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
        <div className="grid gap-3 sm:grid-cols-3">
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

        {mode === "existing" && (
          <div className="space-y-1.5">
            <Label htmlFor="i-client">{t("processes.client")}</Label>
            <Combobox
              id="i-client"
              options={options}
              value={clientId}
              onSelect={setClientId}
              term={clientTerm}
              onTermChange={setClientTerm}
              placeholder={t("processes.searchClient")}
              loading={searching}
              emptyLabel={t("intake.noClients")}
              truncatedLabel={
                truncated
                  ? t("intake.showingSome", { shown: options.length, total })
                  : undefined
              }
            />
          </div>
        )}

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
            disabled={isLoading || (mode === "existing" ? !clientId : !draft.pid.trim())}
          >
            {isLoading && <Spinner />}
            {t("intake.create")}
          </Button>
        </form>
      )}
    </div>
  );
}
