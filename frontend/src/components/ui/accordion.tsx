import { ChevronDown } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

export function Accordion({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("space-y-3", className)} {...props} />;
}

// One independently-expandable section: header (title + right-side meta/badge) over collapsible body.
export function AccordionItem({
  title,
  meta,
  defaultOpen = false,
  children,
}: {
  title: React.ReactNode;
  meta?: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = React.useState(defaultOpen);
  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-start transition-colors hover:bg-muted/40"
      >
        <span className="font-medium">{title}</span>
        <span className="flex items-center gap-3">
          {meta}
          <ChevronDown className={cn("size-4 shrink-0 transition-transform", open && "rotate-180")} />
        </span>
      </button>
      {open && <div className="border-t border-border px-4 py-4">{children}</div>}
    </div>
  );
}
