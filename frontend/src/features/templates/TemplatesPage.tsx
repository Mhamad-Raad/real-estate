import { ChevronDown, ChevronRight, FileText, Info } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PageHeader } from "@/features/common/PageHeader";
import { Pagination } from "@/features/common/Pagination";
import { Skeleton } from "@/components/ui/skeleton";

import { TemplatePreviewDialog } from "./TemplatePreviewDialog";
import { useListTemplateTypesQuery, useListTemplatesQuery } from "./templatesApi";
import type { DocumentTemplate } from "./types";

const kb = (bytes: number) => `${Math.max(1, Math.round(bytes / 1024))} KB`;

// Admin-only, and **view-only** (§6.6, UC-010): templates are installed from the codebase, so
// there is nothing to upload, activate or delete here. Grouped by letter with the active version
// first and retired ones folded away — retired versions are kept for traceability, but showing a
// dozen of them inline buried the two rows that matter (UC-009).
export function TemplatesPage() {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [previewing, setPreviewing] = useState<DocumentTemplate | null>(null);

  const { data, isLoading, isError } = useListTemplatesQuery({ page });
  const { data: types } = useListTemplateTypesQuery();

  const rows = useMemo(() => data?.results ?? [], [data]);
  // One group per letter type the *backend* knows about, so a newly added type appears here
  // rather than silently missing as `case_summary` did (UC-008).
  const groups = useMemo(() => {
    const known = types?.map((type) => type.code) ?? [];
    const seen = [...new Set([...known, ...rows.map((r) => r.template_type)])];
    return seen.map((code) => {
      const forType = rows.filter((r) => r.template_type === code);
      return {
        code,
        active: forType.find((r) => r.is_active) ?? null,
        retired: forType.filter((r) => !r.is_active),
      };
    });
  }, [rows, types]);

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <PageHeader title={t("templates.title")} description={t("templates.subtitle")} />

      <div className="flex items-start gap-2 rounded-md bg-muted px-3 py-2 text-sm text-muted-foreground">
        <Info className="mt-0.5 size-4 shrink-0" />
        {t("templates.readOnlyNote")}
      </div>

      {isLoading && (
        <div className="space-y-3">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      )}

      {isError && (
        <div className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {t("common.loadError")}
        </div>
      )}

      {!isLoading && !isError && groups.length === 0 && (
        <p className="py-10 text-center text-sm text-muted-foreground">{t("templates.empty")}</p>
      )}

      {!isLoading &&
        !isError &&
        groups.map(({ code, active, retired }) => (
          <Card key={code} className="space-y-3 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold">{t(`templates.types.${code}`)}</h2>
                {active ? (
                  <p className="text-xs text-muted-foreground">
                    {active.name} · {active.original_filename || "—"} · {kb(active.size_bytes)}
                  </p>
                ) : (
                  <p className="text-xs text-muted-foreground">{t("templates.empty")}</p>
                )}
              </div>
              <div className="flex items-center gap-2">
                {active ? (
                  <Badge variant="success">{t("templates.active")}</Badge>
                ) : (
                  <Badge variant="neutral">{t("templates.retired")}</Badge>
                )}
                {active && (
                  <Button variant="outline" size="sm" onClick={() => setPreviewing(active)}>
                    <FileText className="size-4" />
                    {t("templates.preview")}
                  </Button>
                )}
              </div>
            </div>

            {retired.length > 0 && (
              <div className="border-t border-border pt-2">
                <button
                  type="button"
                  onClick={() => setExpanded((e) => ({ ...e, [code]: !e[code] }))}
                  aria-expanded={Boolean(expanded[code])}
                  className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                >
                  {expanded[code] ? (
                    <ChevronDown className="size-3.5" />
                  ) : (
                    <ChevronRight className="size-3.5 rtl:rotate-180" />
                  )}
                  {expanded[code]
                    ? t("templates.hideRetired")
                    : t("templates.showRetired", { count: retired.length })}
                </button>
                {expanded[code] && (
                  <ul className="mt-2 space-y-1">
                    {retired.map((template) => (
                      <li
                        key={template.id}
                        className="flex items-center justify-between gap-2 rounded-md px-2 py-1.5 text-xs text-muted-foreground hover:bg-accent/50"
                      >
                        <span className="truncate">
                          {template.name} · {kb(template.size_bytes)}
                        </span>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7"
                          onClick={() => setPreviewing(template)}
                        >
                          {t("templates.preview")}
                        </Button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </Card>
        ))}

      <Pagination page={page} count={data?.count ?? 0} onPage={setPage} />

      <TemplatePreviewDialog template={previewing} onClose={() => setPreviewing(null)} />
    </div>
  );
}
