import { AlertTriangle, FileWarning, FolderKanban, Info, UserPlus, Users } from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAppSelector } from "@/app/hooks";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate, formatNumber } from "@/lib/format";

import { useGetDashboardQuery } from "./dashboardApi";
import { StatCard } from "./StatCard";

// One colour per overall_status, reused by the pie and its legend.
const STATUS_COLORS: Record<string, string> = {
  draft: "var(--color-muted-foreground)",
  in_progress: "var(--color-primary)",
  complete: "var(--color-success)",
  rejected: "var(--color-destructive)",
};

export function DashboardPage() {
  const { t, i18n } = useTranslation();
  const user = useAppSelector((s) => s.auth.user);
  const { data, isLoading, isError } = useGetDashboardQuery();

  const name =
    [user?.first_name, user?.last_name].filter(Boolean).join(" ") || user?.username || "";
  const num = (n: number) => formatNumber(n, i18n.language);
  // Recharts hands the formatter a loose ValueType; only numbers reach these charts.
  const tooltipNumber = (value: unknown) => num(Number(value ?? 0));

  const statusData = Object.entries(data?.processes_by_status ?? {}).map(([key, value]) => ({
    key,
    label: t(`processes.status.${key}`),
    value,
  }));
  const stepData = Object.entries(data?.processes_by_step ?? {}).map(([key, value]) => ({
    label: t("processes.stepShort", { n: key }),
    value,
  }));
  const hasStatusData = statusData.some((row) => row.value > 0);

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">
          {t("dashboard.welcome", { name })}
        </h1>
        <p className="text-muted-foreground">
          {data
            ? t("dashboard.windowOf", { days: data.window_days, date: formatDate(data.window_start, i18n.language) })
            : t("dashboard.subtitle")}
        </p>
      </div>

      {isError && (
        <div className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {t("common.loadError")}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label={t("dashboard.clientsInWindow")}
          value={data?.clients_in_window}
          icon={UserPlus}
          loading={isLoading}
        />
        <StatCard
          label={t("dashboard.processesInWindow")}
          value={data?.processes_in_window}
          hint={t("dashboard.ofTotal", { total: num(data?.processes_total ?? 0) })}
          icon={FolderKanban}
          loading={isLoading}
        />
        <StatCard
          label={t("dashboard.casesMissingFiles")}
          value={data?.processes_missing_files}
          hint={t("dashboard.acrossSteps", { steps: num(data?.steps_missing_files ?? 0) })}
          icon={FileWarning}
          loading={isLoading}
          tone="attention"
        />
        <StatCard
          label={t("dashboard.duplicateFlagged")}
          value={data?.duplicate_flagged}
          hint={t("dashboard.similarNames", { names: num(data?.similar_name_flagged ?? 0) })}
          icon={data?.duplicate_flagged ? AlertTriangle : Info}
          loading={isLoading}
          tone={data?.duplicate_flagged ? "attention" : "default"}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">{t("dashboard.byStatus")}</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-56 w-full" />
            ) : !hasStatusData ? (
              <p className="py-16 text-center text-sm text-muted-foreground">
                {t("common.noData")}
              </p>
            ) : (
              <ResponsiveContainer width="100%" height={224}>
                <PieChart>
                  <Pie data={statusData} dataKey="value" nameKey="label" innerRadius={45}>
                    {statusData.map((row) => (
                      <Cell key={row.key} fill={STATUS_COLORS[row.key]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={tooltipNumber} />
                </PieChart>
              </ResponsiveContainer>
            )}
            <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
              {statusData.map((row) => (
                <li key={row.key} className="flex items-center gap-1.5 text-xs">
                  <span
                    className="size-2.5 rounded-full"
                    style={{ background: STATUS_COLORS[row.key] }}
                  />
                  <span className="text-muted-foreground">{row.label}</span>
                  <span className="font-medium tabular-nums">{num(row.value)}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">{t("dashboard.byStep")}</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-56 w-full" />
            ) : (
              // `reversed` mirrors the axis for RTL so step 1 starts on the correct side.
              <ResponsiveContainer width="100%" height={224}>
                <BarChart data={stepData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.3} />
                  <XAxis dataKey="label" reversed={i18n.dir() === "rtl"} tickLine={false} />
                  <YAxis
                    allowDecimals={false}
                    orientation={i18n.dir() === "rtl" ? "right" : "left"}
                    tickLine={false}
                  />
                  <Tooltip formatter={tooltipNumber} />
                  <Bar dataKey="value" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">{t("dashboard.byLawyer")}</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-20 w-full" />
          ) : !data?.by_lawyer_handled.length ? (
            <p className="py-6 text-center text-sm text-muted-foreground">{t("common.noData")}</p>
          ) : (
            <ul className="divide-y divide-border">
              {data.by_lawyer_handled.map((row) => (
                <li key={row.lawyer_id} className="flex items-center gap-3 py-2 text-sm">
                  <Users className="size-4 shrink-0 text-muted-foreground" />
                  <span className="flex-1 truncate">{row.username}</span>
                  <span className="font-medium tabular-nums">{num(row.count)}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
