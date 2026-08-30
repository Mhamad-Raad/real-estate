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
import { labeller } from "@/lib/fieldLabels";
import { useAutosave, isSettledDate } from "@/hooks/useAutosave";
import { useFieldErrors } from "@/hooks/useFieldErrors";
import { FieldError } from "@/components/ui/field-error";

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
  const { errors, setFromError, clear, clearAll } = useFieldErrors();
  const docs = process.documents.filter((d) => d.institute_entry === entry.id);

  const patch = async (fields: Partial<InstituteEntry>) => {
    try {
      await update({ id: entry.id, process: process.id, version: entry.version, ...fields }).unwrap();
      clearAll();
    } catch (err) {
      // Each control here patches on its own, so the rejected one has to be identifiable —
      // `custom_name` in particular carries a server rule of its own (§3.4).
      setFromError(err);
      toast.error(apiErrorMessage(err, t("common.saveError"), labeller(t), t));
    }
  };

  // Every editable field on the card shares one queue: the typed ones debounce, the dropdowns save
  // at once, and a dropdown change carries any edit still settling out with it in the same patch —
  // so picking a lawyer mid-way through typing a date cannot 409 against it.
  //
  // ⚠️ It does **not** serialise two immediate saves: change both dropdowns inside one round trip
  // and the second still PATCHes the `version` the first has not yet bumped. Pre-existing, and the
  // real fix is a fresh version rather than a longer queue — so the claim stops here.
  const field = useAutosave({
    saved: {
      custom_name: entry.custom_name,
      assigned_lawyer: entry.assigned_lawyer,
      approval_status: entry.approval_status,
      approval_date: entry.approval_date,
    },
    onSave: patch,
  });

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
        {/* The custom name grows into the row rather than sitting under a fixed cap: these are
            full Sorani institute names, and `max-w-xs` cut them off mid-phrase (UC-091). */}
        {entry.is_custom ? (
          <div className="min-w-0 flex-1 space-y-1">
            <Input
              value={field.value("custom_name")}
              disabled={!canEdit}
              placeholder={t("workflow.customName")}
              className="h-8"
              required
              aria-required
              invalid={Boolean(errors.custom_name) || !field.value("custom_name")}
              onChange={(e) => {
                clear("custom_name");
                field.set("custom_name", e.target.value);
              }}
              onBlur={field.flush}
            />
            {/* A red border with no reason says only "something is wrong here". The blank case is
                not a server rejection — the row saves fine — so it carries its own message
                (UC-111); the step's own missing list is the other half of the same rule. */}
            <FieldError
              message={
                errors.custom_name ||
                (field.value("custom_name") ? undefined : t("workflow.customNameRequired"))
              }
            />
          </div>
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
            value={field.value("assigned_lawyer") ?? ""}
            disabled={!canEdit}
            onChange={(e) =>
              field.commit("assigned_lawyer", e.target.value ? Number(e.target.value) : null)
            }
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

        {/* Offered on every institute step (UC-078). The completion rules still differ — step 2
            needs a decision, step 3 a decision and a date, step 4 neither — but the compiled
            report prints both columns for every row, so a step-4 institute that was finished
            still read "pending" and steps 2 and 4 could never be dated at all. */}
        <div className="space-y-1">
          <Label className="text-xs">{t("workflow.approval")}</Label>
          <Select
            value={field.value("approval_status")}
            disabled={!canEdit}
            onChange={(e) => field.commit("approval_status", e.target.value as ApprovalStatus)}
            className="h-9"
          >
            {APPROVALS.map((a) => (
              <option key={a} value={a}>
                {t(`workflow.approvalStatus.${a}`)}
              </option>
            ))}
          </Select>
        </div>

        <div className="space-y-1">
          <Label className="text-xs">{t("workflow.approvalDate")}</Label>
          <Input
            type="date"
            value={field.value("approval_date") ?? ""}
            disabled={!canEdit}
            className="h-9"
            invalid={Boolean(errors.approval_date)}
            onChange={(e) => {
              clear("approval_date");
              // Held on screen until the year is plausible — see `isSettledDate`.
              field.set("approval_date", e.target.value || null, isSettledDate(e.target.value));
            }}
            onBlur={() => {
              if (!isSettledDate(field.value("approval_date") ?? ""))
                field.set("approval_date", entry.approval_date, false);
              field.flush();
            }}
          />
          <FieldError message={errors.approval_date} />
        </div>
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
              // One acceptance per institute (UC-085) — the same capacity the backend enforces.
              disabled={docs.length > 0}
              disabledReason={t("errors.slot.filesFull")}
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
