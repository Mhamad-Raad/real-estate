import { AlertTriangle, Plus, ShieldCheck, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { useAppSelector } from "@/app/hooks";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { toast } from "@/components/ui/toaster";
import { useListCategoriesQuery } from "@/features/categories/categoriesApi";
import { ConfirmDialog } from "@/features/common/ConfirmDialog";
import { PageHeader } from "@/features/common/PageHeader";
import { SelectionToolbar } from "./SelectionToolbar";
import { Pagination } from "@/features/common/Pagination";
import { TableStateRows } from "@/features/common/TableStateRows";
import { apiErrorMessage } from "@/lib/apiError";
import { formatDate } from "@/lib/format";

import { OverrideDialog } from "./OverrideDialog";
import { ProcessCreateDialog } from "./ProcessCreateDialog";
import { useDeleteProcessMutation, useListProcessesQuery } from "./processesApi";
import { OVERALL_STATUSES, type OverallStatus, type ProcessListItem } from "./types";

const STATUS_VARIANT: Record<OverallStatus, BadgeProps["variant"]> = {
  draft: "neutral",
  in_progress: "default",
  complete: "success",
  rejected: "danger",
};

export function ProcessesPage() {
  const { t, i18n } = useTranslation();
  const isAdmin = useAppSelector((s) => s.auth.user?.is_admin ?? false);
  const { data: categories } = useListCategoriesQuery({});

  // Raw text inputs vs the debounced values actually sent to the API (search/pid hit the DB).
  const [searchTerm, setSearchTerm] = useState("");
  const [pidTerm, setPidTerm] = useState("");
  const [search, setSearch] = useState("");
  const [pid, setPid] = useState("");
  const [category, setCategory] = useState<number | "">("");
  const [status, setStatus] = useState<OverallStatus | "">("");
  const [step, setStep] = useState<number | "">("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    const id = setTimeout(() => {
      setSearch(searchTerm.trim());
      setPid(pidTerm.trim());
    }, 300);
    return () => clearTimeout(id);
  }, [searchTerm, pidTerm]);

  // Any filter change resets to the first page (the result set changes).
  useEffect(() => setPage(1), [search, pid, category, status, step]);

  const filters = useMemo(
    () => ({ search, pid, category, overall_status: status, current_step: step, page }),
    [search, pid, category, status, step, page],
  );
  const { data, isLoading, isError, refetch } = useListProcessesQuery(filters);
  const [remove, { isLoading: removing }] = useDeleteProcessMutation();

  const [createOpen, setCreateOpen] = useState(false);
  const [overriding, setOverriding] = useState<ProcessListItem | null>(null);
  const [toDelete, setToDelete] = useState<ProcessListItem | null>(null);
  const [selected, setSelected] = useState<number[]>([]);

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
  const loading = isLoading;
  const allSelected = rows.length > 0 && rows.every((r) => selected.includes(r.id));
  const toggle = (id: number) =>
    setSelected((ids) => (ids.includes(id) ? ids.filter((i) => i !== id) : [...ids, id]));
  const toggleAll = () =>
    setSelected((ids) =>
      allSelected
        ? ids.filter((id) => !rows.some((r) => r.id === id))
        : [...new Set([...ids, ...rows.map((r) => r.id)])],
    );

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHeader
        title={t("processes.title")}
        description={t("processes.subtitle")}
        action={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="size-4" />
            {t("processes.add")}
          </Button>
        }
      />

      <SelectionToolbar selected={selected} onClear={() => setSelected([])} />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Input
          placeholder={t("processes.filters.name")}
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
        <Input
          placeholder={t("processes.filters.pid")}
          value={pidTerm}
          onChange={(e) => setPidTerm(e.target.value)}
        />
        <Select
          value={category}
          onChange={(e) => setCategory(e.target.value ? Number(e.target.value) : "")}
        >
          <option value="">{t("processes.filters.allCategories")}</option>
          {(categories?.results ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {c.code} — {c.name}
            </option>
          ))}
        </Select>
        <Select
          value={status}
          onChange={(e) => setStatus(e.target.value as OverallStatus | "")}
        >
          <option value="">{t("processes.filters.allStatuses")}</option>
          {OVERALL_STATUSES.map((s) => (
            <option key={s} value={s}>
              {t(`processes.status.${s}`)}
            </option>
          ))}
        </Select>
        <Select
          value={step}
          onChange={(e) => setStep(e.target.value ? Number(e.target.value) : "")}
        >
          <option value="">{t("processes.filters.allSteps")}</option>
          {[1, 2, 3, 4, 5].map((n) => (
            <option key={n} value={n}>
              {t("processes.stepShort", { n })}
            </option>
          ))}
        </Select>
      </div>

      <Card className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10">
                <input
                  type="checkbox"
                  className="size-4 align-middle accent-primary"
                  checked={allSelected}
                  onChange={toggleAll}
                  aria-label={t("processes.selectAll")}
                />
              </TableHead>
              <TableHead>{t("processes.client")}</TableHead>
              <TableHead>{t("clients.pid")}</TableHead>
              <TableHead>{t("processes.step")}</TableHead>
              <TableHead>{t("processes.statusLabel")}</TableHead>
              <TableHead>{t("processes.assignedLawyer")}</TableHead>
              <TableHead>{t("processes.createdAt")}</TableHead>
              <TableHead className="w-24 text-end">{t("common.actions")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableStateRows
              colSpan={8}
              isLoading={loading}
              isError={isError}
              isEmpty={rows.length === 0}
              emptyLabel={t("processes.empty")}
              onRetry={refetch}
              skeletonRows={4}
            />
            {!loading &&
              !isError &&
              rows.map((process) => (
                <TableRow key={process.id}>
                  <TableCell>
                    <input
                      type="checkbox"
                      className="size-4 align-middle accent-primary"
                      checked={selected.includes(process.id)}
                      onChange={() => toggle(process.id)}
                      aria-label={t("processes.selectRow")}
                    />
                  </TableCell>
                  <TableCell className="font-medium">
                    <span className="flex items-center gap-2">
                      <Link to={`/processes/${process.id}`} className="text-primary hover:underline">
                        {process.client_full_name}
                      </Link>
                      {process.duplicate_flagged && (
                        <AlertTriangle
                          className="size-4 text-amber-500"
                          aria-label={t("processes.flagged")}
                        />
                      )}
                    </span>
                  </TableCell>
                  <TableCell>{process.client_pid}</TableCell>
                  <TableCell>
                    <Badge variant="neutral">
                      {t("processes.stepShort", { n: process.current_step })}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANT[process.overall_status]}>
                      {t(`processes.status.${process.overall_status}`)}
                    </Badge>
                  </TableCell>
                  <TableCell>{process.assigned_lawyer_username}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDate(process.created_at, i18n.language)}
                  </TableCell>
                  <TableCell className="text-end">
                    <div className="flex justify-end gap-1">
                      {isAdmin && process.duplicate_flagged && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="size-8 text-amber-600"
                          onClick={() => setOverriding(process)}
                          aria-label={t("processes.override.title")}
                        >
                          <ShieldCheck className="size-4" />
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-8 text-destructive"
                        onClick={() => setToDelete(process)}
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

      <ProcessCreateDialog open={createOpen} onClose={() => setCreateOpen(false)} />
      <OverrideDialog process={overriding} onClose={() => setOverriding(null)} />
      <ConfirmDialog
        open={Boolean(toDelete)}
        title={t("processes.deleteTitle")}
        description={t("processes.deleteConfirm", { name: toDelete?.client_full_name ?? "" })}
        onConfirm={confirmDelete}
        onClose={() => setToDelete(null)}
        loading={removing}
      />
    </div>
  );
}
