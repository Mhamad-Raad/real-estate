import * as React from "react";

import { cn } from "@/lib/utils";

// A 1px rule in the border token — heavy enough to group, quiet enough not to compete with content.
export function Separator({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      role="separator"
      className={cn("h-px w-full shrink-0 bg-border", className)}
      {...props}
    />
  );
}

// A titled block within a long form. Step 1 stacks five unrelated concerns (beneficiary, land,
// papers, letter…) and without grouping the eye gets no purchase on it (UC-025).
export function FormSection({
  title,
  description,
  children,
  className,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("space-y-4", className)}>
      <div className="space-y-1">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        {description && (
          <p className="text-xs text-muted-foreground">{description}</p>
        )}
      </div>
      <Separator />
      {children}
    </section>
  );
}
