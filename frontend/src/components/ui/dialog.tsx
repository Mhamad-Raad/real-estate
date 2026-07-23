import * as React from "react";
import { X } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const FOCUSABLE =
  'a[href],button:not([disabled]),textarea,input,select,[tabindex]:not([tabindex="-1"])';

// Lightweight modal — overlay + centered card, closes on Escape or overlay click. No extra deps
// (keeps the offline footprint minimal); logical spacing keeps it correct in RTL. Manages focus:
// traps Tab inside the dialog, focuses the first field on open, and restores focus on close.
export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  className,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}) {
  const { t } = useTranslation();
  const panelRef = React.useRef<HTMLDivElement>(null);
  const titleId = React.useId();

  React.useEffect(() => {
    if (!open) return;
    const restoreTo = document.activeElement as HTMLElement | null;
    document.body.style.overflow = "hidden";

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key !== "Tab" || !panelRef.current) return;
      // Focus trap: keep Tab/Shift+Tab cycling within the dialog's focusable elements.
      const items = panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE);
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKey);
    // Focus the first field (skip the close button) once mounted.
    const focusables = panelRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE);
    (focusables?.[1] ?? focusables?.[0])?.focus();

    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
      restoreTo?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
    >
      <div
        ref={panelRef}
        className={cn(
          "relative w-full max-w-lg rounded-lg border border-border bg-card p-6 shadow-lg",
          className,
        )}
      >
        <Button
          variant="ghost"
          size="icon"
          className="absolute end-3 top-3 size-8"
          onClick={onClose}
          aria-label={t("common.cancel")}
        >
          <X className="size-4" />
        </Button>
        <div className="mb-4 space-y-1 pe-8">
          <h2 id={titleId} className="text-lg font-semibold tracking-tight">
            {title}
          </h2>
          {description && <p className="text-sm text-muted-foreground">{description}</p>}
        </div>
        {children}
      </div>
    </div>
  );
}

// Standard right-aligned (logical) footer for dialog actions.
export function DialogFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("mt-6 flex justify-end gap-2", className)} {...props} />;
}
