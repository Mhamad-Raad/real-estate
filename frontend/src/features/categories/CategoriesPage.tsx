import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

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
import { Pagination } from "@/features/common/Pagination";
import { TableStateRows } from "@/features/common/TableStateRows";
import { apiErrorMessage, apiInUseTotal } from "@/lib/apiError";
import { formatNumber } from "@/lib/format";

import { CategoryFormDialog } from "./CategoryFormDialog";
import { useDeleteCategoryMutation, useListCategoriesQuery } from "./categoriesApi";
import type { Category } from "./types";

export function CategoriesPage() {
  const { t, i18n } = useTranslation();
  const [page, setPage] = useState(1);
  const { data, isLoading, isError, refetch } = useListCategoriesQuery({ page });
  const [remove, { isLoading: removing }] = useDeleteCategoryMutation();
  const [editing, setEditing] = useState<Category | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [toDelete, setToDelete] = useState<Category | null>(null);

  const openCreate = () => {
    setEditing(null);
    setFormOpen(true);
  };
  const openEdit = (category: Category) => {
    setEditing(category);
    setFormOpen(true);
  };

  const confirmDelete = async () => {
    if (!toDelete) return;
    try {
      await remove(toDelete.id).unwrap();
      toast.success(t("common.deleted"));
      setToDelete(null);
    } catch (err) {
      // The server refuses while live cases still belong to this category; say how many.
      const inUse = apiInUseTotal(err);
      toast.error(
        inUse
          ? t("categories.inUse", { total: formatNumber(inUse, i18n.language) })
          : apiErrorMessage(err, t("common.deleteError")),
      );
    }
  };

  const rows = data?.results ?? [];
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <PageHeader
        title={t("categories.title")}
        description={t("categories.subtitle")}
        action={
          <Button onClick={openCreate}>
            <Plus className="size-4" />
            {t("categories.add")}
          </Button>
        }
      />

      <Card className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("categories.code")}</TableHead>
              <TableHead>{t("categories.name")}</TableHead>
              <TableHead className="w-24 text-end">{t("common.actions")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableStateRows
              colSpan={3}
              isLoading={isLoading}
              isError={isError}
              isEmpty={rows.length === 0}
              emptyLabel={t("categories.empty")}
              onRetry={refetch}
            />
            {!isLoading &&
              !isError &&
              rows.map((category) => (
                <TableRow key={category.id}>
                  <TableCell className="font-medium">{category.code}</TableCell>
                  <TableCell>{category.name}</TableCell>
                  <TableCell className="text-end">
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-8"
                        onClick={() => openEdit(category)}
                        aria-label={t("common.edit")}
                      >
                        <Pencil className="size-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-8 text-destructive"
                        onClick={() => setToDelete(category)}
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

      <Pagination page={page} count={data?.count ?? 0} onPage={setPage} />

      <CategoryFormDialog open={formOpen} category={editing} onClose={() => setFormOpen(false)} />
      <ConfirmDialog
        open={Boolean(toDelete)}
        title={t("categories.deleteTitle")}
        description={t("categories.deleteConfirm", { name: toDelete?.name ?? "" })}
        onConfirm={confirmDelete}
        onClose={() => setToDelete(null)}
        loading={removing}
      />
    </div>
  );
}
