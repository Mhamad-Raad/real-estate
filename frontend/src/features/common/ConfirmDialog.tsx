import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Dialog, DialogFooter } from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";

// Reusable destructive-action confirmation (used by every soft-delete in Iteration 1).
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  onConfirm,
  onClose,
  loading = false,
}: {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onClose: () => void;
  loading?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <Dialog open={open} onClose={onClose} title={title} description={description} className="max-w-md">
      <DialogFooter>
        {/* Typed for the same reason every other dialog here is: `Button` sets no default, so an
            untyped one inside a `<form>` submits it. No caller nests this in a form today — the
            duplicate dialog did, and cancelling saved the record (2026-08-30). */}
        <Button type="button" variant="outline" onClick={onClose} disabled={loading}>
          {t("common.cancel")}
        </Button>
        <Button type="button" variant="destructive" onClick={onConfirm} disabled={loading}>
          {loading && <Spinner />}
          {confirmLabel ?? t("common.delete")}
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
