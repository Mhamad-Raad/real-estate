import { Pencil, Plus, Search, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { toast } from "@/components/ui/toaster";
import { ConfirmDialog } from "@/features/common/ConfirmDialog";
import { PageHeader } from "@/features/common/PageHeader";
import { TableStateRows } from "@/features/common/TableStateRows";
import { apiErrorMessage } from "@/lib/apiError";

import { ClientFormDialog } from "./ClientFormDialog";
import { useDeleteClientMutation, useListClientsQuery } from "./clientsApi";
import type { Client } from "./types";

export function ClientsPage() {
  const { t } = useTranslation();
  const [term, setTerm] = useState("");
  const [search, setSearch] = useState("");
  const { data, isLoading, isFetching, isError, refetch } = useListClientsQuery({ search });
  const [remove, { isLoading: removing }] = useDeleteClientMutation();
  const [editing, setEditing] = useState<Client | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [toDelete, setToDelete] = useState<Client | null>(null);

  // Debounce the search box so typing doesn't fire a request per keystroke.
  useEffect(() => {
    const id = setTimeout(() => setSearch(term.trim()), 300);
    return () => clearTimeout(id);
  }, [term]);

  const openCreate = () => {
    setEditing(null);
    setFormOpen(true);
  };
  const openEdit = (client: Client) => {
    setEditing(client);
    setFormOpen(true);
  };

  const confirmDelete = async () => {
    if (!toDelete) return;
    try {
      await remove(toDelete.id).unwrap();
      toast.success(t("common.deleted"));
      setToDelete(null);
    } catch (err) {
      toast.error(apiErrorMessage(err, t("common.deleteError")));
    }
  };

  const rows = data?.results ?? [];
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHeader
        title={t("clients.title")}
        description={t("clients.subtitle")}
        action={
          <Button onClick={openCreate}>
            <Plus className="size-4" />
            {t("clients.add")}
          </Button>
        }
      />

      <div className="relative max-w-sm">
        <Search className="pointer-events-none absolute start-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          className="ps-9"
          placeholder={t("clients.searchPlaceholder")}
          value={term}
          onChange={(e) => setTerm(e.target.value)}
        />
      </div>

      <Card className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("clients.fullName")}</TableHead>
              <TableHead>{t("clients.pid")}</TableHead>
              <TableHead>{t("clients.motherName")}</TableHead>
              <TableHead>{t("clients.maritalStatus")}</TableHead>
              <TableHead className="w-24 text-end">{t("common.actions")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableStateRows
              colSpan={5}
              isLoading={isLoading || isFetching}
              isError={isError}
              isEmpty={rows.length === 0}
              emptyLabel={t("clients.empty")}
              onRetry={refetch}
              skeletonRows={4}
            />
            {!isLoading &&
              !isFetching &&
              !isError &&
              rows.map((client) => (
                <TableRow key={client.id}>
                  <TableCell className="font-medium">{client.full_name}</TableCell>
                  <TableCell>{client.pid}</TableCell>
                  <TableCell>{client.mother_full_name}</TableCell>
                  <TableCell>
                    <Badge variant="neutral">{t(`clients.marital.${client.marital_status}`)}</Badge>
                  </TableCell>
                  <TableCell className="text-end">
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-8"
                        onClick={() => openEdit(client)}
                        aria-label={t("common.edit")}
                      >
                        <Pencil className="size-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-8 text-destructive"
                        onClick={() => setToDelete(client)}
                        aria-label={t("common.delete")}
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
          </TableBody>
        </Table>
      </Card>

      <ClientFormDialog open={formOpen} client={editing} onClose={() => setFormOpen(false)} />
      <ConfirmDialog
        open={Boolean(toDelete)}
        title={t("clients.deleteTitle")}
        description={t("clients.deleteConfirm", { name: toDelete?.full_name ?? "" })}
        onConfirm={confirmDelete}
        onClose={() => setToDelete(null)}
        loading={removing}
      />
    </div>
  );
}
