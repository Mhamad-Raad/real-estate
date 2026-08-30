import * as React from "react";

import { cn } from "@/lib/utils";

// `invalid` paints the border and ring destructive and sets `aria-invalid`, so the field that
// caused a save to fail is identifiable by sight AND by a screen reader. Kept on the primitive
// rather than passed as a className by each form: the office reads these screens in three
// languages, and a red border is the one cue that survives every one of them.
export const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }
>(({ className, type, invalid, ...props }, ref) => (
  <input
    type={type}
    ref={ref}
    aria-invalid={invalid || undefined}
    className={cn(
      "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50",
      invalid && "border-destructive focus-visible:ring-destructive",
      className,
    )}
    {...props}
  />
));
Input.displayName = "Input";
