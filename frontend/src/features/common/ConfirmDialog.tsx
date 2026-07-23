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
        <Button variant="outline" onClick={onClose} disabled={loading}>
          {t("common.cancel")}
        </Button>
        <Button variant="destructive" onClick={onConfirm} disabled={loading}>
          {loading && <Spinner />}
          {confirmLabel ?? t("common.delete")}
        </Button>
      </DialogFooter>
    </Dialog>
  );
}
