import { Undo2 } from "lucide-react";
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
import { apiErrorMessage } from "@/lib/apiError";
import { formatDate, formatNumber } from "@/lib/format";

import {
  useListDeletedClientsQuery,
  useListDeletedProcessesQuery,
  useRestoreClientMutation,
  useRestoreProcessMutation,
} from "./deletedApi";

type Tab = "processes" | "clients";

/**
 * The admin restore desk (UC-063). Nothing in this system is ever hard-deleted (§11.1) — but until
 * now the deleted rows were invisible, so `restore` could only be reached by someone who already
 * knew the id. This is where a mistaken delete is undone.
 *
 * Cases and beneficiaries are two tabs of one page because they are deleted together: removing a
 * case releases its beneficiary so the person can be entered again (UC-061), and restoring the
 * case brings them back with it.
 */
export function DeletedPage() {
  const { t, i18n } = useTranslation();
  const [tab, setTab] = useState<Tab>("processes");
  // A page each: switching tabs must not carry the other list's position across.
  const [casePage, setCasePage] = useState(1);
  const [clientPage, setClientPage] = useState(1);
  const [confirming, setConfirming] = useState<{ kind: Tab; id: number; label: string } | null>(
    null,
  );

  const processes = useListDeletedProcessesQuery(casePage);
  const clients = useListDeletedClientsQuery(clientPage);
  const [restoreProcess, { isLoading: restoringProcess }] = useRestoreProcessMutation();
  const [restoreClient, { isLoading: restoringClient }] = useRestoreClientMutation();

  const active = tab === "processes" ? processes : clients;
  const processRows = processes.data?.results ?? [];
  const clientRows = clients.data?.results ?? [];
  // The **total**, not the page — a tab reading "25" when 60 are deleted would be a silent cap.
  const caseCount = processes.data?.count ?? 0;
  const clientCount = clients.data?.count ?? 0;

  const confirmRestore = async () => {
    if (!confirming) return;
    try {
      if (confirming.kind === "processes") await restoreProcess(confirming.id).unwrap();
      else await restoreClient(confirming.id).unwrap();
      toast.success(t("deleted.restored"));
      setConfirming(null);
    } catch (err) {
      // The commonest failure is a national ID taken by a re-entry since the delete — which is
      // the freed-PID rule working, not a fault. The server names it; show what it said.
      toast.error(apiErrorMessage(err, t("deleted.restoreError")));
      setConfirming(null);
    }
  };

  const TABS: { key: Tab; label: string; count: number }[] = [
    { key: "processes", label: t("deleted.cases"), count: caseCount },
    { key: "clients", label: t("deleted.clients"), count: clientCount },
  ];

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <PageHeader title={t("deleted.title")} description={t("deleted.subtitle")} />

      <div className="flex gap-2">
        {TABS.map(({ key, label, count }) => (
          <Button
            key={key}
            type="button"
            variant={tab === key ? "default" : "outline"}
            aria-pressed={tab === key}
            onClick={() => setTab(key)}
          >
            {label}
            <span className="text-xs opacity-70">{formatNumber(count, i18n.language)}</span>
          </Button>
        ))}
      </div>

      <Card className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              {tab === "processes" ? (
                <>
                  <TableHead>{t("workflow.uniqueCode")}</TableHead>
                  <TableHead>{t("processes.client")}</TableHead>
                </>
              ) : (
                <>
                  <TableHead>{t("clients.fullName")}</TableHead>
                  <TableHead>{t("clients.pid")}</TableHead>
                </>
              )}
              <TableHead>{t("deleted.deletedAt")}</TableHead>
              <TableHead className="w-32 text-end">{t("common.actions")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableStateRows
              colSpan={4}
              isLoading={active.isLoading}
              isError={active.isError}
              isEmpty={(tab === "processes" ? processRows : clientRows).length === 0}
              emptyLabel={t("deleted.empty")}
              onRetry={active.refetch}
            />
            {!active.isLoading &&
              !active.isError &&
              tab === "processes" &&
              processRows.map((row) => (
                <TableRow key={row.id}>
                  {/* Quoted on paper left-to-right, even on an RTL page. */}
                  <TableCell className="font-mono text-xs" dir="ltr">
                    {row.unique_code || "—"}
                  </TableCell>
                  <TableCell>{row.client_full_name}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {row.deleted_at ? formatDate(row.deleted_at, i18n.language) : "—"}
                  </TableCell>
                  <TableCell className="text-end">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        setConfirming({
                          kind: "processes",
                          id: row.id,
                          label: row.unique_code || row.client_full_name,
                        })
                      }
                    >
                      <Undo2 className="size-4" />
                      {t("deleted.restore")}
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            {!active.isLoading &&
              !active.isError &&
              tab === "clients" &&
              clientRows.map((row) => (
                <TableRow key={row.id}>
                  <TableCell className="font-medium">{row.full_name}</TableCell>
                  <TableCell className="font-mono text-xs" dir="ltr">
                    {row.pid}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {row.deleted_at ? formatDate(row.deleted_at, i18n.language) : "—"}
                  </TableCell>
                  <TableCell className="text-end">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        setConfirming({ kind: "clients", id: row.id, label: row.full_name })
                      }
                    >
                      <Undo2 className="size-4" />
                      {t("deleted.restore")}
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
          </TableBody>
        </Table>
      </Card>

      <Pagination
        page={tab === "processes" ? casePage : clientPage}
        count={tab === "processes" ? caseCount : clientCount}
        onPage={tab === "processes" ? setCasePage : setClientPage}
      />

      <ConfirmDialog
        open={Boolean(confirming)}
        title={t("deleted.confirmTitle")}
        description={t("deleted.confirmBody", { name: confirming?.label ?? "" })}
        confirmLabel={t("deleted.restore")}
        loading={restoringProcess || restoringClient}
        onConfirm={confirmRestore}
        onClose={() => setConfirming(null)}
      />
    </div>
  );
}
