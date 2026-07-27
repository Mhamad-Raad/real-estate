import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toaster";
import { useUpdateClientMutation } from "@/features/clients/clientsApi";
import type { Client, MaritalStatus } from "@/features/clients/types";
import { apiErrorMessage } from "@/lib/apiError";

const MARITAL: MaritalStatus[] = ["single", "married", "divorced", "widowed"];

// The beneficiary's own details, edited from inside Step 1 — the generated letter prints exactly
// these fields, so the lawyer fills them where the work happens rather than on the clients page.
export function ClientDetailsPanel({
  client,
  canEdit,
}: {
  client: Client;
  canEdit: boolean;
}) {
  const { t } = useTranslation();
  const [update, { isLoading }] = useUpdateClientMutation();

  const [dob, setDob] = useState(client.date_of_birth ?? "");
  const [marital, setMarital] = useState<MaritalStatus>(client.marital_status);
  const [spouseName, setSpouseName] = useState(client.spouse_name);
  const [spouseDob, setSpouseDob] = useState(client.spouse_date_of_birth ?? "");
  const [spouseMother, setSpouseMother] = useState(client.spouse_mother_full_name);

  useEffect(() => {
    setDob(client.date_of_birth ?? "");
    setMarital(client.marital_status);
    setSpouseName(client.spouse_name);
    setSpouseDob(client.spouse_date_of_birth ?? "");
    setSpouseMother(client.spouse_mother_full_name);
  }, [
    client.id,
    client.date_of_birth,
    client.marital_status,
    client.spouse_name,
    client.spouse_date_of_birth,
    client.spouse_mother_full_name,
  ]);

  const married = marital === "married";
  const dirty =
    dob !== (client.date_of_birth ?? "") ||
    marital !== client.marital_status ||
    spouseName !== client.spouse_name ||
    spouseDob !== (client.spouse_date_of_birth ?? "") ||
    spouseMother !== client.spouse_mother_full_name;

  // The server requires all three spouse fields together, so don't offer a save that would 400.
  const complete = Boolean(dob) && (!married || Boolean(spouseName && spouseDob && spouseMother));

  const save = async () => {
    try {
      await update({
        id: client.id,
        version: client.version,
        date_of_birth: dob || null,
        marital_status: marital,
        // Blank the spouse fields when there is no spouse, so a former one never reaches the letter.
        spouse_name: married ? spouseName : "",
        spouse_date_of_birth: married ? spouseDob || null : null,
        spouse_mother_full_name: married ? spouseMother : "",
      }).unwrap();
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(apiErrorMessage(err, t("common.saveError")));
    }
  };

  return (
    <div className="space-y-3 rounded-md border border-border p-3">
      <p className="text-sm font-medium">{t("workflow.clientDetails")}</p>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="s1-dob">{t("clients.dateOfBirth")}</Label>
          <Input
            id="s1-dob"
            type="date"
            value={dob}
            disabled={!canEdit}
            onChange={(e) => setDob(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="s1-marital">{t("clients.maritalStatus")}</Label>
          <Select
            id="s1-marital"
            value={marital}
            disabled={!canEdit}
            onChange={(e) => setMarital(e.target.value as MaritalStatus)}
          >
            {MARITAL.map((m) => (
              <option key={m} value={m}>
                {t(`clients.marital.${m}`)}
              </option>
            ))}
          </Select>
        </div>
      </div>

      {married && (
        <div className="space-y-3 border-t border-border pt-3">
          <p className="text-xs font-medium text-muted-foreground">{t("workflow.spouseSection")}</p>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="s1-spouse">{t("clients.spouseName")}</Label>
              <Input
                id="s1-spouse"
                value={spouseName}
                disabled={!canEdit}
                onChange={(e) => setSpouseName(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="s1-spouse-dob">{t("clients.spouseDateOfBirth")}</Label>
              <Input
                id="s1-spouse-dob"
                type="date"
                value={spouseDob}
                disabled={!canEdit}
                onChange={(e) => setSpouseDob(e.target.value)}
              />
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor="s1-spouse-mother">{t("clients.spouseMotherName")}</Label>
              <Input
                id="s1-spouse-mother"
                value={spouseMother}
                disabled={!canEdit}
                onChange={(e) => setSpouseMother(e.target.value)}
              />
            </div>
          </div>
        </div>
      )}

      {canEdit && (
        <Button size="sm" onClick={save} disabled={isLoading || !dirty || !complete}>
          {isLoading && <Spinner />}
          {t("workflow.saveClient")}
        </Button>
      )}
    </div>
  );
}
