import { AlertTriangle, FileStack, Plus, ShieldCheck, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";

import { useAppSelector } from "@/app/hooks";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
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
import { toast } from "@/lib/toast";
import { useListCategoriesQuery } from "@/features/categories/categoriesApi";
import { ConfirmDialog } from "@/features/common/ConfirmDialog";
import { LinkRow } from "@/features/common/LinkRow";
import { PageHeader } from "@/features/common/PageHeader";
import { SelectionToolbar } from "./SelectionToolbar";
import { Pagination } from "@/features/common/Pagination";
import { TableStateRows } from "@/features/common/TableStateRows";
import { apiErrorMessage } from "@/lib/apiError";
import { useNum } from "@/hooks/useNum";
import { formatDate } from "@/lib/format";

import { OverrideDialog } from "./OverrideDialog";
import { useDeleteProcessMutation, useListProcessesQuery } from "./processesApi";
import { OVERALL_STATUSES, STEP_NUMBERS, type OverallStatus, type ProcessListItem } from "./types";

const STATUS_VARIANT: Record<OverallStatus, BadgeProps["variant"]> = {
  draft: "neutral",
  in_progress: "default",
  complete: "success",
  rejected: "danger",
};

// A URL value is untrusted: a number that is not one, or a status not in the list, reads as unset.
const numParam = (raw: string | null): number | "" => {
  const n = Number(raw);
  return raw && Number.isInteger(n) && n > 0 ? n : "";
};
const enumParam = <T extends string>(raw: string | null, allowed: readonly T[]): T | "" =>
  allowed.includes(raw as T) ? (raw as T) : "";

export function ProcessesPage() {
  const { t, i18n } = useTranslation();
  const isAdmin = useAppSelector((s) => s.auth.user?.is_admin ?? false);
  const num = useNum();
  const { data: categories } = useListCategoriesQuery();

  // The filters and the page live in the URL (UC-124): a visit to a case and the way back —
  // browser Back or the list button — lands on the same URL, so the list comes back as it was
  // left. Also how a link lands here pre-filtered: the Clients page sends a national ID (UC-026).
  const [params, setParams] = useSearchParams();
  const search = params.get("search") ?? "";
  const category = numParam(params.get("category"));
  const status = enumParam(params.get("status"), OVERALL_STATUSES);
  const step = numParam(params.get("step"));
  const page = numParam(params.get("page")) || 1;

  // Replaced in place so each keystroke is not a history entry; any filter change resets to
  // the first page (the result set changes). Writing the same value is skipped so the mount's
  // debounced search echo does not wipe the page.
  const setParam = useCallback(
    (key: string, value: string | number) => {
      setParams(
        (prev) => {
          const text = String(value);
          if ((prev.get(key) ?? "") === text) return prev;
          const next = new URLSearchParams(prev);
          if (text === "") next.delete(key);
          else next.set(key, text);
          if (key !== "page") next.delete("page");
          return next;
        },
        { replace: true },
      );
    },
    [setParams],
  );

  // The box owns its own text; the URL gets the settled value.
  const [searchTerm, setSearchTerm] = useState(search);
  useEffect(() => {
    const id = setTimeout(() => setParam("search", searchTerm.trim()), 300);
    return () => clearTimeout(id);
  }, [searchTerm, setParam]);

  const filters = useMemo(
    () => ({ search, category, overall_status: status, current_step: step, page }),
    [search, category, status, step, page],
  );
  const { data, isLoading, isError, refetch } = useListProcessesQuery(filters);
  const [remove, { isLoading: removing }] = useDeleteProcessMutation();

  const navigate = useNavigate();
  const location = useLocation();
  // The way into a case remembers this URL, so its "back to list" button returns here.
  const listUrl = `${location.pathname}${location.search}`;
  const [overriding, setOverriding] = useState<ProcessListItem | null>(null);
  const [toDelete, setToDelete] = useState<ProcessListItem | null>(null);
  const [selected, setSelected] = useState<number[]>([]);

  // Ticks are scoped to what is on screen: keeping them across a filter or page change would
  // silently print rows the user can no longer see (§6.8).
  useEffect(() => {
    setSelected([]);
  }, [search, category, status, step, page]);

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
          <div className="flex flex-wrap gap-2">
            {/* Beside the ordinary button, not in the nav: it belongs to the backlog run and
                leaves with it (UC-114). */}
            <Button variant="outline" onClick={() => navigate("/processes/fast-entry")}>
              <FileStack className="size-4" />
              {t("fastEntry.title")}
            </Button>
            <Button onClick={() => navigate("/processes/new")}>
              <Plus className="size-4" />
              {t("processes.add")}
            </Button>
          </div>
        }
      />

      <SelectionToolbar
        selected={selected}
        onClear={() => setSelected([])}
        stepById={Object.fromEntries(
          (data?.results ?? []).map((p) => [p.id, p.current_step]),
        )}
      />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {/* One box for the three things a lawyer knows about a case — the name, the national ID
            and the office's own code. There were two boxes, both searching an ID (§4.3). */}
        <Input
          className="sm:col-span-2"
          placeholder={t("processes.filters.search")}
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
        <Select
          value={category}
          onChange={(e) => setParam("category", e.target.value)}
        >
          <option value="">{t("processes.filters.allCategories")}</option>
          {(categories ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {c.code} — {c.name}
            </option>
          ))}
        </Select>
        <Select
          value={status}
          onChange={(e) => setParam("status", e.target.value)}
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
          onChange={(e) => setParam("step", e.target.value)}
        >
          <option value="">{t("processes.filters.allSteps")}</option>
          {STEP_NUMBERS.map((n) => (
            <option key={n} value={n}>
              {t("processes.stepShort", { n: num(n) })}
            </option>
          ))}
        </Select>
      </div>

      <Card className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10">
                <Checkbox
                  checked={allSelected}
                  indeterminate={selected.length > 0 && !allSelected}
                  onChange={toggleAll}
                  aria-label={t("processes.selectAll")}
                />
              </TableHead>
              <TableHead>{t("workflow.uniqueCode")}</TableHead>
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
                <LinkRow key={process.id} to={`/processes/${process.id}`} state={{ from: listUrl }}>
                  <TableCell>
                    <Checkbox
                      checked={selected.includes(process.id)}
                      onChange={() => toggle(process.id)}
                      aria-label={t("processes.selectRow")}
                    />
                  </TableCell>
                  {/* The office quotes this code on paper, so it reads left-to-right even in RTL. */}
                  <TableCell className="font-mono text-xs" dir="ltr">
                    {process.unique_code || "—"}
                  </TableCell>
                  <TableCell className="font-medium">
                    <span className="flex items-center gap-2">
                      <Link
                        to={`/processes/${process.id}`}
                        state={{ from: listUrl }}
                        className="text-primary hover:underline"
                      >
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
                      {t("processes.stepShort", { n: num(process.current_step) })}
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
                </LinkRow>
              ))}
          </TableBody>
        </Table>
      </Card>

      <Pagination page={page} count={data?.count ?? 0} onPage={(p) => setParam("page", p)} />

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
