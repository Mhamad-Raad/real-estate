import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toaster";
import { ClientFields } from "@/features/clients/ClientFields";
import { toInput, withMaritalRules } from "@/features/clients/clientForm";
import { useUpdateClientMutation } from "@/features/clients/clientsApi";
import type { Client, ClientInput } from "@/features/clients/types";
import { apiErrorMessage } from "@/lib/apiError";

// The beneficiary's own details, edited from inside Step 1 — the generated letter prints exactly
// these fields, so the lawyer fills them where the work happens rather than on the Clients page,
// which is now search-only (§8, UC-026).
//
// Uses the shared `ClientFields` rather than its own inputs: this panel used to carry five fields
// while the record has thirteen, so a scanned beneficiary's place of birth, address and phone could
// not be entered anywhere once the Clients page stopped editing (UC-030).
export function ClientDetailsPanel({
  client,
  canEdit,
}: {
  client: Client;
  canEdit: boolean;
}) {
  const { t } = useTranslation();
  const [update, { isLoading }] = useUpdateClientMutation();
  const [form, setForm] = useState<ClientInput>(() => toInput(client));

  // Re-seed when the server's copy changes — a save elsewhere (or a card confirmation) must not be
  // silently overwritten by whatever is sitting in this form.
  useEffect(() => {
    setForm(toInput(client));
  }, [client]);

  const saved = toInput(client);
  const dirty = JSON.stringify(form) !== JSON.stringify(saved);
  const married = form.marital_status === "married";
  // The server requires all three spouse fields together, so don't offer a save that would 400.
  const complete =
    Boolean(form.date_of_birth) &&
    (!married ||
      Boolean(form.spouse_name && form.spouse_date_of_birth && form.spouse_mother_full_name));

  const save = async () => {
    try {
      await update({
        id: client.id,
        version: client.version,
        ...withMaritalRules(form),
      }).unwrap();
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(apiErrorMessage(err, t("common.saveError")));
    }
  };

  return (
    <div className="space-y-3 rounded-md border border-border p-3">
      <p className="text-sm font-medium">{t("workflow.clientDetails")}</p>

      {/* The case's category is asked once in the land section; a second one here would be two
          controls for what the office thinks of as one thing. */}
      <fieldset disabled={!canEdit} className="contents">
        <ClientFields value={form} onChange={setForm} idPrefix="s1" showCategory={false} />
      </fieldset>

      {canEdit && (
        <Button size="sm" onClick={save} disabled={isLoading || !dirty || !complete}>
          {isLoading && <Spinner />}
          {t("workflow.saveClient")}
        </Button>
      )}
    </div>
  );
}
