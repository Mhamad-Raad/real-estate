import { ChevronDown, Lock } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Present when the group is single-open: the parent owns which item is expanded, so opening one
 * closes the rest (UC-051). Absent for a plain group, where each item keeps its own state and
 * several may stand open at once.
 */
const SingleOpenContext = React.createContext<{
  openKey: string | null;
  setOpenKey: (key: string | null) => void;
} | null>(null);

export function Accordion({
  single = false,
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { single?: boolean }) {
  const [openKey, setOpenKey] = React.useState<string | null>(null);
  const value = React.useMemo(() => ({ openKey, setOpenKey }), [openKey]);
  const body = (
    <div className={cn("space-y-3", className)} {...props}>
      {children}
    </div>
  );
  return single ? (
    <SingleOpenContext.Provider value={value}>{body}</SingleOpenContext.Provider>
  ) : (
    body
  );
}

// One expandable section: header (title + right-side meta/badge) over collapsible body.
// `locked` renders it greyed out and un-openable — the body is never mounted.
export function AccordionItem({
  itemKey,
  title,
  meta,
  defaultOpen = false,
  locked = false,
  children,
}: {
  /** Identifies this item inside a single-open group; ignored by a plain group. */
  itemKey?: string;
  title: React.ReactNode;
  meta?: React.ReactNode;
  defaultOpen?: boolean;
  locked?: boolean;
  children: React.ReactNode;
}) {
  const group = React.useContext(SingleOpenContext);
  const key = itemKey ?? "";
  const [localOpen, setLocalOpen] = React.useState(defaultOpen && !locked);
  const setOpenKey = group?.setOpenKey;

  // A section that becomes the default one (the step the lawyer is actually on) must reveal
  // itself — the initial state is evaluated once and items never remount. In a single-open group
  // this is also what lands the user on `current_step` when the page loads.
  React.useEffect(() => {
    if (!defaultOpen || locked) return;
    if (setOpenKey) setOpenKey(key);
    else setLocalOpen(true);
  }, [defaultOpen, locked, key, setOpenKey]);

  const open = group ? group.openKey === key : localOpen;
  const expanded = open && !locked;

  const toggle = () => {
    if (group) group.setOpenKey(open ? null : key);
    else setLocalOpen((o) => !o);
  };

  return (
    <div
      className={cn(
        "overflow-hidden rounded-lg border border-border bg-card",
        locked && "opacity-60",
      )}
    >
      <button
        type="button"
        onClick={toggle}
        disabled={locked}
        aria-expanded={expanded}
        className={cn(
          "flex w-full items-center justify-between gap-3 px-4 py-3 text-start transition-colors",
          locked ? "cursor-not-allowed text-muted-foreground" : "hover:bg-muted/40",
        )}
      >
        <span className="font-medium">{title}</span>
        <span className="flex items-center gap-3">
          {meta}
          {locked ? (
            <Lock className="size-4 shrink-0" />
          ) : (
            <ChevronDown
              className={cn("size-4 shrink-0 transition-transform", expanded && "rotate-180")}
            />
          )}
        </span>
      </button>
      {expanded && <div className="border-t border-border px-4 py-4">{children}</div>}
    </div>
  );
}
