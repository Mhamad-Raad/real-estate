import { CheckCircle2, Trash2, Upload } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

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
import { Pagination } from "@/features/common/Pagination";
import { TableStateRows } from "@/features/common/TableStateRows";
import { apiErrorMessage } from "@/lib/apiError";

import { TemplateUploadDialog } from "./TemplateUploadDialog";
import {
  useActivateTemplateMutation,
  useDeleteTemplateMutation,
  useListTemplatesQuery,
} from "./templatesApi";
import type { DocumentTemplate } from "./types";

const kb = (bytes: number) => `${Math.max(1, Math.round(bytes / 1024))} KB`;

// Admin-only screen for the .docx letter templates (§6.6). Exactly one template per type is
// active — activating one retires the other, which is why this is a radio-like action, not a flag.
export function TemplatesPage() {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const { data, isLoading, isError, refetch } = useListTemplatesQuery({ page });
  const [activate, { isLoading: activating }] = useActivateTemplateMutation();
  const [remove, { isLoading: removing }] = useDeleteTemplateMutation();
  const [uploadOpen, setUploadOpen] = useState(false);
  const [toDelete, setToDelete] = useState<DocumentTemplate | null>(null);

  const makeActive = async (template: DocumentTemplate) => {
    try {
      await activate({ id: template.id, version: template.version }).unwrap();
      toast.success(t("templates.activated"));
    } catch (err) {
      toast.error(apiErrorMessage(err, t("common.saveError")));
    }
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
    <div className="mx-auto max-w-5xl space-y-6">
      <PageHeader
        title={t("templates.title")}
        description={t("templates.subtitle")}
        action={
          <Button onClick={() => setUploadOpen(true)}>
            <Upload className="size-4" />
            {t("templates.upload")}
          </Button>
        }
      />

      <Card className="overflow-hidden p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("templates.name")}</TableHead>
              <TableHead>{t("templates.type")}</TableHead>
              <TableHead>{t("templates.fileColumn")}</TableHead>
              <TableHead>{t("templates.statusLabel")}</TableHead>
              <TableHead className="w-28 text-end">{t("common.actions")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableStateRows
              colSpan={5}
              isLoading={isLoading}
              isError={isError}
              isEmpty={rows.length === 0}
              emptyLabel={t("templates.empty")}
              onRetry={refetch}
              skeletonRows={3}
            />
            {!isLoading &&
              !isError &&
              rows.map((template) => (
                <TableRow key={template.id}>
                  <TableCell className="font-medium">{template.name}</TableCell>
                  <TableCell>{t(`templates.types.${template.template_type}`)}</TableCell>
                  <TableCell className="text-muted-foreground">
                    <span className="block max-w-52 truncate">
                      {template.original_filename || "—"}
                    </span>
                    <span className="text-xs">{kb(template.size_bytes)}</span>
                  </TableCell>
                  <TableCell>
                    {template.is_active ? (
                      <Badge variant="success">{t("templates.active")}</Badge>
                    ) : (
                      <Badge variant="neutral">{t("templates.retired")}</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-end">
                    <div className="flex items-center justify-end gap-1">
                      {!template.is_active && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="size-8"
                          disabled={activating}
                          onClick={() => makeActive(template)}
                          aria-label={t("templates.activate")}
                          title={t("templates.activate")}
                        >
                          <CheckCircle2 className="size-4" />
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-8 text-destructive"
                        onClick={() => setToDelete(template)}
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

      <TemplateUploadDialog open={uploadOpen} onClose={() => setUploadOpen(false)} />

      <ConfirmDialog
        open={Boolean(toDelete)}
        title={t("templates.deleteTitle")}
        description={
          toDelete?.is_active
            ? t("templates.deleteActiveConfirm", { name: toDelete.name })
            : t("templates.deleteConfirm", { name: toDelete?.name ?? "" })
        }
        confirmLabel={t("common.delete")}
        loading={removing}
        onConfirm={confirmDelete}
        onClose={() => setToDelete(null)}
      />
    </div>
  );
}
