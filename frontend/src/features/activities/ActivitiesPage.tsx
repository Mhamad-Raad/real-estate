import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
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
import { PageHeader } from "@/features/common/PageHeader";
import { Pagination } from "@/features/common/Pagination";
import { TableStateRows } from "@/features/common/TableStateRows";
import { formatDate } from "@/lib/format";

import { ActivityDetailDialog } from "./ActivityDetailDialog";
import { useGetActivityVocabularyQuery, useListActivitiesQuery } from "./activitiesApi";
import type { Activity, ActivityAction, ActivityFilters } from "./types";

// Destructive and exceptional actions stand out; routine ones stay quiet.
const ACTION_VARIANT: Record<ActivityAction, "default" | "neutral" | "success" | "warning" | "danger"> = {
  create: "success",
  update: "default",
  delete: "danger",
  restore: "warning",
  verify: "success",
  override: "warning",
  generate: "default",
  login: "neutral",
  logout: "neutral",
};

export function ActivitiesPage() {
  const { t, i18n } = useTranslation();
  const [filters, setFilters] = useState<ActivityFilters>({});
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Activity | null>(null);

  const { data, isLoading, isError, refetch } = useListActivitiesQuery({ ...filters, page });
  const { data: vocabulary } = useGetActivityVocabularyQuery();

  // Any filter change invalidates the current page number — page 4 of the old result set is
  // meaningless against the new one, and can land the user on an empty page.
  useEffect(() => {
    setPage(1);
  }, [filters]);

  const set = (key: keyof ActivityFilters, value: string) =>
    setFilters((prev) => ({ ...prev, [key]: value }));

  return (
    <div className="space-y-6">
      <PageHeader title={t("nav.activities")} description={t("activities.subtitle")} />

      <Card>
        <CardContent className="grid gap-4 p-4 sm:grid-cols-2 lg:grid-cols-5">
          <div className="space-y-1.5">
            <Label htmlFor="ac-actor">{t("activities.actor")}</Label>
            <Select
              id="ac-actor"
              value={filters.actor ?? ""}
              onChange={(e) => set("actor", e.target.value)}
            >
              <option value="">{t("activities.allActors")}</option>
              {(vocabulary?.actors ?? []).map((user) => (
                <option key={user.id} value={user.id}>
                  {user.username}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="ac-action">{t("activities.actionLabel")}</Label>
            <Select
              id="ac-action"
              value={filters.action ?? ""}
              onChange={(e) => set("action", e.target.value)}
            >
              <option value="">{t("activities.allActions")}</option>
              {(vocabulary?.actions ?? []).map((action) => (
                <option key={action.value} value={action.value}>
                  {t(`activities.action.${action.value}`, { defaultValue: action.label })}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="ac-entity">{t("activities.entity")}</Label>
            <Select
              id="ac-entity"
              value={filters.entity_type ?? ""}
              onChange={(e) => set("entity_type", e.target.value)}
            >
              <option value="">{t("activities.allEntities")}</option>
              {(vocabulary?.entity_types ?? []).map((entity) => (
                <option key={entity} value={entity}>
                  {entity}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="ac-from">{t("reports.dateFrom")}</Label>
            <Input
              id="ac-from"
              type="date"
              value={filters.created_after ?? ""}
              onChange={(e) => set("created_after", e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="ac-to">{t("reports.dateTo")}</Label>
            <Input
              id="ac-to"
              type="date"
              value={filters.created_before ?? ""}
              onChange={(e) => set("created_before", e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("activities.when")}</TableHead>
                <TableHead>{t("activities.actor")}</TableHead>
                <TableHead>{t("activities.actionLabel")}</TableHead>
                <TableHead>{t("activities.entity")}</TableHead>
                <TableHead>{t("activities.ip")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableStateRows
                colSpan={5}
                isLoading={isLoading}
                isError={isError}
                isEmpty={!data?.results.length}
                emptyLabel={t("activities.empty")}
                onRetry={refetch}
              />
              {(data?.results ?? []).map((activity) => (
                <TableRow
                  key={activity.id}
                  className="cursor-pointer"
                  onClick={() => setSelected(activity)}
                >
                  <TableCell className="text-muted-foreground">
                    {formatDate(activity.created_at, i18n.language, {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </TableCell>
                  <TableCell className="font-medium">
                    {activity.actor_username || t("activities.systemActor")}
                  </TableCell>
                  <TableCell>
                    <Badge variant={ACTION_VARIANT[activity.action] ?? "neutral"}>
                      {t(`activities.action.${activity.action}`, { defaultValue: activity.action })}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {activity.entity_type}
                    {activity.entity_id && ` #${activity.entity_id}`}
                  </TableCell>
                  {/* dir=ltr so an IPv4 address doesn't scramble inside the RTL layout. */}
                  <TableCell dir="ltr" className="text-start text-muted-foreground">
                    {activity.ip_address || "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Pagination page={page} count={data?.count ?? 0} onPage={setPage} />

      <ActivityDetailDialog activity={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
