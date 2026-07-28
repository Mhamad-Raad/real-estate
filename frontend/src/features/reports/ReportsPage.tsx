import { Download } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import { useAppSelector } from "@/app/hooks";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useListCategoriesQuery } from "@/features/categories/categoriesApi";
import { PageHeader } from "@/features/common/PageHeader";
import { TableStateRows } from "@/features/common/TableStateRows";
import { downloadFile } from "@/features/documents/download";
import { formatNumber } from "@/lib/format";

import { reportCsvUrl, useGetProcessReportQuery, useGetUserReportQuery } from "./reportsApi";
import type { ReportFilters } from "./types";

export function ReportsPage() {
  const { t, i18n } = useTranslation();
  const token = useAppSelector((s) => s.auth.access);
  const [filters, setFilters] = useState<ReportFilters>({});

  const processReport = useGetProcessReportQuery(filters);
  const userReport = useGetUserReportQuery(filters);
  const { data: categories } = useListCategoriesQuery({});

  const num = (n: number) => formatNumber(n, i18n.language);
  const set = (key: keyof ReportFilters, value: string) =>
    setFilters((prev) => ({ ...prev, [key]: value }));

  const exportCsv = async (kind: "processes" | "users") => {
    try {
      await downloadFile(reportCsvUrl(kind, filters), `${kind}-report.csv`, token);
    } catch {
      toast.error(t("reports.exportError"));
    }
  };

  const statusRows = Object.entries(processReport.data?.by_status ?? {});

  return (
    <div className="space-y-6">
      <PageHeader title={t("nav.reports")} description={t("reports.subtitle")} />

      <Card>
        <CardContent className="grid gap-4 p-4 sm:grid-cols-3">
          <div className="space-y-1.5">
            <Label htmlFor="rp-from">{t("reports.dateFrom")}</Label>
            <Input
              id="rp-from"
              type="date"
              value={filters.date_from ?? ""}
              onChange={(e) => set("date_from", e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="rp-to">{t("reports.dateTo")}</Label>
            <Input
              id="rp-to"
              type="date"
              value={filters.date_to ?? ""}
              onChange={(e) => set("date_to", e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="rp-cat">{t("processes.category")}</Label>
            <Select
              id="rp-cat"
              value={String(filters.category ?? "")}
              onChange={(e) => set("category", e.target.value)}
            >
              <option value="">{t("processes.filters.allCategories")}</option>
              {(categories?.results ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between gap-2">
          <CardTitle className="text-sm font-medium">
            {t("reports.processesTitle")}
            {processReport.data && (
              <span className="ms-2 text-muted-foreground">
                {t("reports.totalCases", { count: processReport.data.total })}
              </span>
            )}
          </CardTitle>
          <Button variant="outline" size="sm" onClick={() => exportCsv("processes")}>
            <Download className="size-4" />
            {t("reports.exportCsv")}
          </Button>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("processes.statusLabel")}</TableHead>
                <TableHead className="text-end">{t("reports.count")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableStateRows
                colSpan={2}
                isLoading={processReport.isLoading}
                isError={processReport.isError}
                isEmpty={!statusRows.length}
                emptyLabel={t("common.noData")}
                onRetry={processReport.refetch}
              />
              {!processReport.isLoading &&
                statusRows.map(([key, count]) => (
                  <TableRow key={key}>
                    <TableCell>{t(`processes.status.${key}`)}</TableCell>
                    <TableCell className="text-end tabular-nums">{num(count)}</TableCell>
                  </TableRow>
                ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between gap-2">
          <CardTitle className="text-sm font-medium">{t("reports.usersTitle")}</CardTitle>
          <Button variant="outline" size="sm" onClick={() => exportCsv("users")}>
            <Download className="size-4" />
            {t("reports.exportCsv")}
          </Button>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("reports.lawyer")}</TableHead>
                <TableHead className="text-end">{t("reports.assigned")}</TableHead>
                <TableHead className="text-end">{t("processes.status.in_progress")}</TableHead>
                <TableHead className="text-end">{t("processes.status.complete")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableStateRows
                colSpan={4}
                isLoading={userReport.isLoading}
                isError={userReport.isError}
                isEmpty={!userReport.data?.length}
                emptyLabel={t("common.noData")}
                onRetry={userReport.refetch}
              />
              {(userReport.data ?? []).map((row) => (
                <TableRow key={row.lawyer_id}>
                  <TableCell className="font-medium">{row.username}</TableCell>
                  <TableCell className="text-end tabular-nums">{num(row.assigned)}</TableCell>
                  <TableCell className="text-end tabular-nums">{num(row.in_progress)}</TableCell>
                  <TableCell className="text-end tabular-nums">{num(row.completed)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
