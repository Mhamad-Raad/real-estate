import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Dialog, DialogFooter } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/lib/toast";
import { apiErrorMessage } from "@/lib/apiError";

import { useOverrideDuplicateMutation } from "./processesApi";
import type { MatchReason, ProcessListItem } from "./types";

const REASONS: MatchReason[] = ["mother_name", "pid"];

// Admin-only: clear a process's duplicate warning with a mandatory reason (logged) (§5.7).
export function OverrideDialog({
  process,
  onClose,
}: {
  process: ProcessListItem | null;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [override, { isLoading }] = useOverrideDuplicateMutation();
  const [matchReason, setMatchReason] = useState<MatchReason>("mother_name");
  const [reason, setReason] = useState("");

  useEffect(() => {
    if (process) {
      setMatchReason("mother_name");
      setReason("");
    }
  }, [process]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!process) return;
    try {
      await override({
        id: process.id,
        match_reason: matchReason,
        reason,
        version: process.version,
      }).unwrap();
      toast.success(t("processes.override.done"));
      onClose();
    } catch (err) {
      toast.error(apiErrorMessage(err, t("common.saveError")));
    }
  };

  return (
    <Dialog
      open={Boolean(process)}
      onClose={onClose}
      title={t("processes.override.title")}
      description={t("processes.override.subtitle")}
    >
      <form onSubmit={submit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="o-reason-type">{t("processes.override.matchReason")}</Label>
          <Select
            id="o-reason-type"
            value={matchReason}
            onChange={(e) => setMatchReason(e.target.value as MatchReason)}
          >
            {REASONS.map((r) => (
              <option key={r} value={r}>
                {t(`processes.override.reason.${r}`)}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="o-reason">{t("processes.override.reasonLabel")}</Label>
          <Textarea
            id="o-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder={t("processes.override.reasonPlaceholder")}
            required
          />
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} disabled={isLoading}>
            {t("common.cancel")}
          </Button>
          <Button type="submit" disabled={isLoading || !reason.trim()}>
            {isLoading && <Spinner />}
            {t("processes.override.confirm")}
          </Button>
        </DialogFooter>
      </form>
    </Dialog>
  );
}
