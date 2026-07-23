import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useAppSelector } from "@/app/hooks";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
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

import { UserFormDialog } from "./UserFormDialog";
import { useDeleteUserMutation, useListUsersQuery } from "./usersApi";
import type { AdminUser } from "./types";

export function UsersPage() {
  const { t } = useTranslation();
  const currentUserId = useAppSelector((s) => s.auth.user?.id);
  const { data, isLoading, isError, refetch } = useListUsersQuery();
  const [remove, { isLoading: removing }] = useDeleteUserMutation();
  const [editing, setEditing] = useState<AdminUser | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [toDelete, setToDelete] = useState<AdminUser | null>(null);

  const openCreate = () => {
    setEditing(null);
    setFormOpen(true);
  };
  const openEdit = (user: AdminUser) => {
    setEditing(user);
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

  const fullName = (u: AdminUser) =>
    [u.first_name, u.last_name].filter(Boolean).join(" ") || "—";
  const rows = data?.results ?? [];

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <PageHeader
        title={t("users.title")}
        description={t("users.subtitle")}
        action={
          <Button onClick={openCreate}>
            <Plus className="size-4" />
            {t("users.add")}
          </Button>
        }
      />

      <Card className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("users.username")}</TableHead>
              <TableHead>{t("users.name")}</TableHead>
              <TableHead>{t("users.role")}</TableHead>
              <TableHead className="w-24 text-end">{t("common.actions")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableStateRows
              colSpan={4}
              isLoading={isLoading}
              isError={isError}
              isEmpty={rows.length === 0}
              emptyLabel={t("users.empty")}
              onRetry={refetch}
            />
            {!isLoading &&
              !isError &&
              rows.map((user) => (
                <TableRow key={user.id}>
                  <TableCell className="font-medium">{user.username}</TableCell>
                  <TableCell>{fullName(user)}</TableCell>
                  <TableCell>
                    <Badge variant={user.is_admin ? "default" : "neutral"}>
                      {t(`role.${user.role}`)}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-end">
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-8"
                        onClick={() => openEdit(user)}
                        aria-label={t("common.edit")}
                      >
                        <Pencil className="size-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-8 text-destructive"
                        onClick={() => setToDelete(user)}
                        disabled={user.id === currentUserId}
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

      <UserFormDialog open={formOpen} user={editing} onClose={() => setFormOpen(false)} />
      <ConfirmDialog
        open={Boolean(toDelete)}
        title={t("users.deleteTitle")}
        description={t("users.deleteConfirm", { name: toDelete?.username ?? "" })}
        onConfirm={confirmDelete}
        onClose={() => setToDelete(null)}
        loading={removing}
      />
    </div>
  );
}
