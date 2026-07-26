import { ChevronDown, Lock } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

export function Accordion({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("space-y-3", className)} {...props} />;
}

// One independently-expandable section: header (title + right-side meta/badge) over collapsible body.
// `locked` renders it greyed out and un-openable — the body is never mounted.
export function AccordionItem({
  title,
  meta,
  defaultOpen = false,
  locked = false,
  children,
}: {
  title: React.ReactNode;
  meta?: React.ReactNode;
  defaultOpen?: boolean;
  locked?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = React.useState(defaultOpen && !locked);
  const expanded = open && !locked;
  return (
    <div
      className={cn(
        "overflow-hidden rounded-lg border border-border bg-card",
        locked && "opacity-60",
      )}
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
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
