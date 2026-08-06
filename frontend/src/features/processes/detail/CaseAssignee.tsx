import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/lib/toast";
import { apiErrorMessage } from "@/lib/apiError";
import { useListLawyersQuery } from "@/features/users/lawyersApi";

import { useReassignProcessMutation } from "../processesApi";
import type { ProcessDetail } from "../types";

/**
 * Who owns this case — shown to everyone, changeable by an admin (2026-08-06).
 *
 * Any lawyer may open a case in a colleague's name, so a mistyped name has to be fixable: no other
 * endpoint touches `assigned_lawyer`, and the assignee is exactly who may edit the case, so a wrong
 * one would lock the right lawyer out for good. Admin-only because it moves work between people —
 * the same reason the duplicate override is (§7.2).
 */
export function CaseAssignee({ process, isAdmin }: { process: ProcessDetail; isAdmin: boolean }) {
  const { t } = useTranslation();
  const { data: lawyers = [] } = useListLawyersQuery(undefined, { skip: !isAdmin });
  const [selected, setSelected] = useState<number | "">(process.assigned_lawyer ?? "");
  const [reassign, { isLoading }] = useReassignProcessMutation();

  useEffect(
    () => setSelected(process.assigned_lawyer ?? ""),
    [process.assigned_lawyer, process.id],
  );

  const save = async () => {
    if (selected === "") return;
    try {
      await reassign({
        id: process.id,
        assigned_lawyer: selected,
        version: process.version,
      }).unwrap();
      toast.success(t("workflow.reassigned"));
    } catch (err) {
      toast.error(apiErrorMessage(err, t("common.saveError")));
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{t("workflow.assignedLawyer")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {isAdmin ? (
          <>
            <div className="flex flex-wrap items-end gap-2">
              <Select
                value={selected}
                onChange={(e) => setSelected(e.target.value ? Number(e.target.value) : "")}
                className="h-9 w-56"
                aria-label={t("workflow.assignedLawyer")}
              >
                {lawyers.map((lawyer) => (
                  <option key={lawyer.id} value={lawyer.id}>
                    {lawyer.username}
                  </option>
                ))}
              </Select>
              <Button
                size="sm"
                onClick={save}
                disabled={isLoading || selected === "" || selected === process.assigned_lawyer}
              >
                {isLoading && <Spinner />}
                {t("workflow.reassign")}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">{t("workflow.reassignHint")}</p>
          </>
        ) : (
          // Plain text for a lawyer: the server would refuse the write anyway, and a disabled
          // control that never becomes enabled reads as broken rather than as "not yours".
          <p className="text-sm">{process.assigned_lawyer_username || t("common.none")}</p>
        )}
      </CardContent>
    </Card>
  );
}
