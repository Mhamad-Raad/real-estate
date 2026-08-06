import { Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { toast } from "@/lib/toast";
import { DocumentRow } from "@/features/documents/DocumentRow";
import { DocumentUpload } from "@/features/documents/DocumentUpload";
import type { Lawyer } from "@/features/users/lawyersApi";
import { apiErrorMessage } from "@/lib/apiError";

import { useDeleteEntryMutation, useUpdateEntryMutation } from "../processesApi";
import type { ApprovalStatus, InstituteEntry, ProcessDetail } from "../types";

const APPROVALS: ApprovalStatus[] = ["pending", "approved", "rejected"];

// One institute submission (§5.1): assigned lawyer, approval/date (steps 2–3), and its document.
export function InstituteEntryCard({
  process,
  entry,
  label,
  lawyers,
  canEdit,
}: {
  process: ProcessDetail;
  entry: InstituteEntry;
  label: string;
  lawyers: Lawyer[];
  canEdit: boolean;
}) {
  const { t } = useTranslation();
  const [update] = useUpdateEntryMutation();
  const [remove, { isLoading: removing }] = useDeleteEntryMutation();
  const docs = process.documents.filter((d) => d.institute_entry === entry.id);

  const patch = async (fields: Partial<InstituteEntry>) => {
    try {
      await update({ id: entry.id, process: process.id, version: entry.version, ...fields }).unwrap();
    } catch (err) {
      toast.error(apiErrorMessage(err, t("common.saveError")));
    }
  };

  const del = async () => {
    try {
      await remove({ id: entry.id, process: process.id }).unwrap();
    } catch (err) {
      toast.error(apiErrorMessage(err, t("common.deleteError")));
    }
  };

  return (
    <div className="space-y-3 rounded-lg border border-border p-3">
      <div className="flex items-center justify-between gap-2">
        {entry.is_custom ? (
          <Input
            defaultValue={entry.custom_name}
            disabled={!canEdit}
            placeholder={t("workflow.customName")}
            className="h-8 max-w-xs"
            onBlur={(e) => e.target.value !== entry.custom_name && patch({ custom_name: e.target.value })}
          />
        ) : (
          <span className="font-medium">{label}</span>
        )}
        {canEdit && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-7 text-destructive"
            onClick={del}
            disabled={removing}
            aria-label={t("common.delete")}
          >
            <Trash2 className="size-4" />
          </Button>
        )}
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <Label className="text-xs">{t("workflow.assignedLawyer")}</Label>
          <Select
            value={entry.assigned_lawyer ?? ""}
            disabled={!canEdit}
            onChange={(e) => patch({ assigned_lawyer: e.target.value ? Number(e.target.value) : null })}
            className="h-9"
          >
            <option value="">{t("common.none")}</option>
            {lawyers.map((l) => (
              <option key={l.id} value={l.id}>
                {l.username}
              </option>
            ))}
          </Select>
        </div>

        {entry.step_number !== 4 && (
          <div className="space-y-1">
            <Label className="text-xs">{t("workflow.approval")}</Label>
            <Select
              value={entry.approval_status}
              disabled={!canEdit}
              onChange={(e) => patch({ approval_status: e.target.value as ApprovalStatus })}
              className="h-9"
            >
              {APPROVALS.map((a) => (
                <option key={a} value={a}>
                  {t(`workflow.approvalStatus.${a}`)}
                </option>
              ))}
            </Select>
          </div>
        )}

        {entry.step_number === 3 && (
          <div className="space-y-1">
            <Label className="text-xs">{t("workflow.approvalDate")}</Label>
            <Input
              type="date"
              value={entry.approval_date ?? ""}
              disabled={!canEdit}
              className="h-9"
              onChange={(e) => patch({ approval_date: e.target.value || null })}
            />
          </div>
        )}
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          {/* Named for the body that issues it, not the generic "Document" — the office asked
              for the Step-4 slot to read "The relevant authority acceptance" (UC-066), and the
              stored file is already named after the institute (§6.7), so the two now agree. */}
          <Label className="text-xs">
            {label ? t("workflow.instituteAcceptance", { name: label }) : t("workflow.document")}
          </Label>
          {canEdit && (
            <DocumentUpload
              process={process.id}
              step={entry.step_number}
              documentType="InstituteDoc"
              instituteEntry={entry.id}
              label={t("workflow.import")}
            />
          )}
        </div>
        {docs.length ? (
          docs.map((d) => <DocumentRow key={d.id} doc={d} />)
        ) : (
          <p className="text-xs text-muted-foreground">{t("workflow.noFile")}</p>
        )}
      </div>
    </div>
  );
}
