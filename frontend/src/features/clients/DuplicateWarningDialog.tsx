import { AlertTriangle } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogFooter } from "@/components/ui/dialog";

import type { Client, DuplicateCheckResult } from "./types";

// Shows possible-duplicate matches before saving a client (§5.7). A PID-exact hit is a hard
// duplicate (the DB will reject an identical active PID); mother-name hits are usually siblings.
export function DuplicateWarningDialog({
  open,
  result,
  onProceed,
  onClose,
}: {
  open: boolean;
  result: DuplicateCheckResult | null;
  onProceed: () => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const pid = result?.pid_matches ?? [];
  const household = result?.household_matches ?? [];
  const mother = result?.mother_name_matches ?? [];
  // Both are hard duplicates, but they are shown apart: telling a lawyer "same National ID"
  // about their applicant's spouse would simply be untrue (§5.7).
  const hardBlock = pid.length > 0 || household.length > 0;

  const line = (c: Client) => (
    <li key={c.id} className="flex items-center justify-between gap-2 rounded-md bg-muted/60 px-3 py-2">
      <span className="font-medium">{c.full_name}</span>
      <span className="text-xs text-muted-foreground">{t("clients.pid")}: {c.pid}</span>
    </li>
  );

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={t("clients.duplicate.title")}
      description={t("clients.duplicate.subtitle")}
    >
      <div className="space-y-4">
        {pid.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm font-medium text-destructive">
              <AlertTriangle className="size-4" />
              {t("clients.duplicate.pidHeading")}
              <Badge variant="danger">{t("clients.duplicate.hard")}</Badge>
            </div>
            <ul className="space-y-1 text-sm">{pid.map(line)}</ul>
          </div>
        )}
        {household.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm font-medium text-destructive">
              <AlertTriangle className="size-4" />
              {t("clients.duplicate.householdHeading")}
              <Badge variant="danger">{t("clients.duplicate.hard")}</Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              {t("clients.duplicate.householdNote")}
            </p>
            <ul className="space-y-1 text-sm">{household.map(line)}</ul>
          </div>
        )}
        {mother.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm font-medium text-amber-600 dark:text-amber-400">
              <AlertTriangle className="size-4" />
              {t("clients.duplicate.motherHeading")}
              <Badge variant="warning">{t("clients.duplicate.soft")}</Badge>
            </div>
            <ul className="space-y-1 text-sm">{mother.map(line)}</ul>
          </div>
        )}
      </div>
      <DialogFooter>
        <Button variant="outline" onClick={onClose}>
          {t("common.cancel")}
        </Button>
        {/* PID-exact matches are blocked outright; only soft (sibling) matches may proceed. */}
        <Button variant={hardBlock ? "outline" : "default"} onClick={onProceed} disabled={hardBlock}>
          {t("clients.duplicate.proceed")}
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
