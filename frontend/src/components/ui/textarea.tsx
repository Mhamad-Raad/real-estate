import * as React from "react";

import { cn } from "@/lib/utils";

// `invalid` matches `Input` and `Select` — a rejected field is marked the same way whichever
// control holds it, so a form author never has to ask which primitive supports what.
export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement> & { invalid?: boolean }
>(({ className, invalid, ...props }, ref) => (
  <textarea
    ref={ref}
    aria-invalid={invalid || undefined}
    className={cn(
      "flex min-h-20 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50",
      invalid && "border-destructive focus-visible:ring-destructive",
      className,
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";
