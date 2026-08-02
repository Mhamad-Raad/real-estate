import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Dialog, DialogFooter } from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toaster";
import { apiErrorMessage } from "@/lib/apiError";

import { ClientFields } from "./ClientFields";
import { EMPTY_CLIENT, withMaritalRules } from "./clientForm";
import { DuplicateWarningDialog } from "./DuplicateWarningDialog";
import {
  useCheckDuplicateMutation,
  useCreateClientMutation,
  useUpdateClientMutation,
} from "./clientsApi";
import type { Client, ClientInput, DuplicateCheckResult } from "./types";

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
  const [checkDuplicate, { isLoading: checking }] = useCheckDuplicateMutation();
  const [create, { isLoading: creating }] = useCreateClientMutation();
  const [update, { isLoading: updating }] = useUpdateClientMutation();
  const [form, setForm] = useState<ClientInput>(EMPTY_CLIENT);
  const [warning, setWarning] = useState<DuplicateCheckResult | null>(null);

  useEffect(() => {
    if (open) {
      setForm(client ? toInput(client) : EMPTY_CLIENT);
      setWarning(null);
    }
  }, [open, client]);

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
    const payload = withMaritalRules(form);
    try {
      const result = await checkDuplicate({
        pid: payload.pid,
        mother_full_name: payload.mother_full_name,
        // Without this the household rule (§5.7) could never fire from this form.
        spouse_pid: payload.spouse_pid,
        exclude_id: client?.id,
      }).unwrap();
      if (
        result.pid_matches.length ||
        result.household_matches.length ||
        result.mother_name_matches.length
      ) {
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

  return (
    <>
      <Dialog
        open={open}
        onClose={onClose}
        title={client ? t("clients.edit") : t("clients.add")}
        className="max-w-2xl"
      >
        <form onSubmit={submit} className="space-y-4">
          <ClientFields value={form} onChange={setForm} />
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
