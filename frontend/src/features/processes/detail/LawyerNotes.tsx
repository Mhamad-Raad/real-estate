import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toaster";
import { apiErrorMessage } from "@/lib/apiError";

import { useUpdateProcessMutation } from "../processesApi";
import type { ProcessDetail } from "../types";

// Free-text notes editable across all steps by the assignee/admin; every change is audited (§5).
export function LawyerNotes({ process, canEdit }: { process: ProcessDetail; canEdit: boolean }) {
  const { t } = useTranslation();
  const [notes, setNotes] = useState(process.lawyer_notes);
  const [update, { isLoading }] = useUpdateProcessMutation();

  useEffect(() => setNotes(process.lawyer_notes), [process.lawyer_notes, process.id]);

  const save = async () => {
    try {
      await update({ id: process.id, version: process.version, lawyer_notes: notes }).unwrap();
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(apiErrorMessage(err, t("common.saveError")));
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{t("workflow.lawyerNotes")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <Textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          disabled={!canEdit}
          placeholder={t("workflow.notesPlaceholder")}
        />
        {canEdit && (
          <Button size="sm" onClick={save} disabled={isLoading || notes === process.lawyer_notes}>
            {isLoading && <Spinner />}
            {t("common.save")}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
