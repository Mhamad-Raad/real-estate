import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Dialog, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toaster";
import { useListCategoriesQuery } from "@/features/categories/categoriesApi";
import { apiErrorMessage } from "@/lib/apiError";

import { DuplicateWarningDialog } from "./DuplicateWarningDialog";
import {
  useCheckDuplicateMutation,
  useCreateClientMutation,
  useUpdateClientMutation,
} from "./clientsApi";
import type { Client, ClientInput, DuplicateCheckResult, MaritalStatus } from "./types";

const MARITAL: MaritalStatus[] = ["single", "married", "divorced", "widowed"];

const EMPTY: ClientInput = {
  full_name: "",
  pid: "",
  mother_full_name: "",
  marital_status: "single",
  spouse_name: "",
  spouse_pid: "",
  spouse_date_of_birth: null,
  spouse_mother_full_name: "",
  date_of_birth: null,
  place_of_birth: "",
  address: "",
  phone: "",
  category: null,
};

// Map a saved Client to the editable input shape (drops server-owned fields like id/version).
function toInput(client: Client): ClientInput {
  return {
    full_name: client.full_name,
    pid: client.pid,
    mother_full_name: client.mother_full_name,
    marital_status: client.marital_status,
    spouse_name: client.spouse_name,
    spouse_date_of_birth: client.spouse_date_of_birth,
    spouse_mother_full_name: client.spouse_mother_full_name,
    spouse_pid: client.spouse_pid,
    date_of_birth: client.date_of_birth,
    place_of_birth: client.place_of_birth,
    address: client.address,
    phone: client.phone,
    category: client.category,
  };
}

// Create/edit a client. Runs the pre-save duplicate check (§5.7); if it fires, the warning dialog
// gates the save (PID-exact blocks; mother-name matches may proceed).
export function ClientFormDialog({
  open,
  client,
  onClose,
}: {
  open: boolean;
  client: Client | null;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const { data: categories } = useListCategoriesQuery({});
  const [checkDuplicate, { isLoading: checking }] = useCheckDuplicateMutation();
  const [create, { isLoading: creating }] = useCreateClientMutation();
  const [update, { isLoading: updating }] = useUpdateClientMutation();
  const [form, setForm] = useState<ClientInput>(EMPTY);
  const [warning, setWarning] = useState<DuplicateCheckResult | null>(null);

  useEffect(() => {
    if (open) {
      setForm(client ? toInput(client) : EMPTY);
      setWarning(null);
    }
  }, [open, client]);

  const set =
    (key: keyof ClientInput) => (e: { target: { value: string } }) =>
      setForm((f) => ({ ...f, [key]: e.target.value }));

  const save = async (data: ClientInput) => {
    try {
      if (client) {
        await update({ id: client.id, version: client.version, ...data }).unwrap();
      } else {
        await create(data).unwrap();
      }
      toast.success(t("common.saved"));
      setWarning(null);
      onClose();
    } catch (err) {
      toast.error(apiErrorMessage(err, t("common.saveError")));
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const married = form.marital_status === "married";
    const payload: ClientInput = {
      ...form,
      date_of_birth: form.date_of_birth || null,
      // Drop spouse details a change of status left behind, so they never reach the letter.
      spouse_name: married ? form.spouse_name : "",
      spouse_date_of_birth: married ? form.spouse_date_of_birth || null : null,
      spouse_mother_full_name: married ? form.spouse_mother_full_name : "",
    };
    try {
      const result = await checkDuplicate({
        pid: payload.pid,
        mother_full_name: payload.mother_full_name,
        exclude_id: client?.id,
      }).unwrap();
      if (result.pid_matches.length || result.mother_name_matches.length) {
        setForm(payload);
        setWarning(result);
        return; // hold the save until the user resolves the warning
      }
      await save(payload);
    } catch (err) {
      toast.error(apiErrorMessage(err, t("common.saveError")));
    }
  };

  const busy = checking || creating || updating;
  const catOptions = categories?.results ?? [];

  return (
    <>
      <Dialog
        open={open}
        onClose={onClose}
        title={client ? t("clients.edit") : t("clients.add")}
        className="max-w-2xl"
      >
        <form onSubmit={submit} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="c-name">{t("clients.fullName")}</Label>
              <Input id="c-name" value={form.full_name} onChange={set("full_name")} required autoFocus />
            </div>
            <div className="space-y-2">
              <Label htmlFor="c-pid">{t("clients.pid")}</Label>
              <Input id="c-pid" value={form.pid} onChange={set("pid")} required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="c-mother">{t("clients.motherName")}</Label>
              <Input id="c-mother" value={form.mother_full_name} onChange={set("mother_full_name")} required />
            </div>
            <div className="space-y-2">
              <Label htmlFor="c-marital">{t("clients.maritalStatus")}</Label>
              <Select id="c-marital" value={form.marital_status} onChange={set("marital_status")}>
                {MARITAL.map((m) => (
                  <option key={m} value={m}>
                    {t(`clients.marital.${m}`)}
                  </option>
                ))}
              </Select>
            </div>
            {/* The generated letter prints a spouse row of name / birth date / mother's name,
                so a married client needs all three (§6.6). */}
            {form.marital_status === "married" && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="c-spouse">{t("clients.spouseName")}</Label>
                  <Input id="c-spouse" value={form.spouse_name} onChange={set("spouse_name")} required />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="c-spouse-dob">{t("clients.spouseDateOfBirth")}</Label>
                  <Input
                    id="c-spouse-dob"
                    type="date"
                    value={form.spouse_date_of_birth ?? ""}
                    onChange={set("spouse_date_of_birth")}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="c-spouse-mother">{t("clients.spouseMotherName")}</Label>
                  <Input
                    id="c-spouse-mother"
                    value={form.spouse_mother_full_name}
                    onChange={set("spouse_mother_full_name")}
                    required
                  />
                </div>
              </>
            )}
            <div className="space-y-2">
              <Label htmlFor="c-dob">{t("clients.dateOfBirth")}</Label>
              <Input
                id="c-dob"
                type="date"
                value={form.date_of_birth ?? ""}
                onChange={set("date_of_birth")}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="c-pob">{t("clients.placeOfBirth")}</Label>
              <Input id="c-pob" value={form.place_of_birth} onChange={set("place_of_birth")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="c-phone">{t("clients.phone")}</Label>
              <Input id="c-phone" value={form.phone} onChange={set("phone")} />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="c-address">{t("clients.address")}</Label>
              <Input id="c-address" value={form.address} onChange={set("address")} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="c-category">{t("clients.category")}</Label>
              <Select
                id="c-category"
                value={form.category ?? ""}
                onChange={(e) =>
                  setForm((f) => ({ ...f, category: e.target.value ? Number(e.target.value) : null }))
                }
              >
                <option value="">{t("common.none")}</option>
                {catOptions.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.code} — {c.name}
                  </option>
                ))}
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={busy}>
              {busy && <Spinner />}
              {t("common.save")}
            </Button>
          </DialogFooter>
        </form>
      </Dialog>

      <DuplicateWarningDialog
        open={Boolean(warning)}
        result={warning}
        onProceed={() => save(form)}
        onClose={() => setWarning(null)}
      />
    </>
  );
}
