import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { useAppSelector } from "@/app/hooks";
import { Button } from "@/components/ui/button";
import { Dialog, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toaster";
import { useListCategoriesQuery } from "@/features/categories/categoriesApi";
import { useListClientsQuery } from "@/features/clients/clientsApi";
import { useListParcelsQuery } from "@/features/parcels/parcelsApi";
import { useListUsersQuery } from "@/features/users/usersApi";
import { apiErrorMessage, apiErrorStatus } from "@/lib/apiError";

import { useCreateProcessMutation } from "./processesApi";

// Create an allocation (Step-1 header): pick the client, optional category/parcel, and — for
// admins — the process-wide assigned lawyer. A duplicate active allocation returns 409 (§5.7).
export function ProcessCreateDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useTranslation();
  const isAdmin = useAppSelector((s) => s.auth.user?.is_admin ?? false);
  const { data: categories } = useListCategoriesQuery({}, { skip: !open });
  const { data: parcels } = useListParcelsQuery(undefined, { skip: !open });
  const { data: users } = useListUsersQuery({}, { skip: !open || !isAdmin });
  const [create, { isLoading }] = useCreateProcessMutation();

  const [client, setClient] = useState("");
  const [category, setCategory] = useState("");
  const [parcel, setParcel] = useState("");
  const [lawyer, setLawyer] = useState("");

  // Searchable client picker: the list is server-searched (debounced) so it isn't capped at page 1.
  const [clientTerm, setClientTerm] = useState("");
  const [clientSearch, setClientSearch] = useState("");
  const { data: clients } = useListClientsQuery({ search: clientSearch }, { skip: !open });

  useEffect(() => {
    if (open) {
      setClient("");
      setCategory("");
      setParcel("");
      setLawyer("");
      setClientTerm("");
      setClientSearch("");
    }
  }, [open]);

  useEffect(() => {
    const id = setTimeout(() => setClientSearch(clientTerm.trim()), 300);
    return () => clearTimeout(id);
  }, [clientTerm]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await create({
        client: Number(client),
        category: category ? Number(category) : null,
        parcel: parcel ? Number(parcel) : null,
        ...(isAdmin && lawyer ? { assigned_lawyer: Number(lawyer) } : {}),
      }).unwrap();
      toast.success(t("processes.created"));
      onClose();
    } catch (err) {
      const msg =
        apiErrorStatus(err) === 409
          ? t("processes.duplicateAllocation")
          : apiErrorMessage(err, t("common.saveError"));
      toast.error(msg);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} title={t("processes.add")} description={t("processes.addSubtitle")}>
      <form onSubmit={submit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="p-client">{t("processes.client")}</Label>
          <Input
            value={clientTerm}
            onChange={(e) => setClientTerm(e.target.value)}
            placeholder={t("processes.searchClient")}
          />
          <Select id="p-client" value={client} onChange={(e) => setClient(e.target.value)} required>
            <option value="" disabled>
              {t("processes.selectClient")}
            </option>
            {(clients?.results ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.full_name} — {c.pid}
              </option>
            ))}
          </Select>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="p-category">{t("processes.category")}</Label>
            <Select id="p-category" value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">{t("common.none")}</option>
              {(categories?.results ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.code} — {c.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="p-parcel">{t("processes.parcel")}</Label>
            <Select id="p-parcel" value={parcel} onChange={(e) => setParcel(e.target.value)}>
              <option value="">{t("common.none")}</option>
              {(parcels?.results ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.parcel_number}
                </option>
              ))}
            </Select>
          </div>
        </div>
        {isAdmin && (
          <div className="space-y-2">
            <Label htmlFor="p-lawyer">{t("processes.assignedLawyer")}</Label>
            <Select id="p-lawyer" value={lawyer} onChange={(e) => setLawyer(e.target.value)}>
              <option value="">{t("processes.assignSelf")}</option>
              {(users?.results ?? []).map((u) => (
                <option key={u.id} value={u.id}>
                  {u.username}
                </option>
              ))}
            </Select>
          </div>
        )}
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} disabled={isLoading}>
            {t("common.cancel")}
          </Button>
          <Button type="submit" disabled={isLoading || !client}>
            {isLoading && <Spinner />}
            {t("common.create")}
          </Button>
        </DialogFooter>
      </form>
    </Dialog>
  );
}
