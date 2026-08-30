import * as React from "react";

import { cn } from "@/lib/utils";

// The chevron is drawn by us, not the OS: a native arrow sits hard against the border, and renders
// differently on the office's Windows hosts than in dev. Inlined as a data URI — no icon font, no
// CDN (§12 offline). `currentColor` cannot be used inside a background image, so the stroke is
// baked to the muted-foreground grey, which stays legible on both themes.
const CHEVRON =
  "url(\"data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%23808c85' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E\")";

// Styled native <select> — fully offline, keyboard/RTL-correct for free, matches Input styling.
//
// `invalid` mirrors `Input`'s, and is not cosmetic parity: `category` is required at intake and
// answers with a field error of its own, so without this the one control that can block a case
// from opening was the one control that could not show it had.
export const Select = React.forwardRef<
  HTMLSelectElement,
  React.SelectHTMLAttributes<HTMLSelectElement> & { invalid?: boolean }
>(({ className, style, invalid, ...props }, ref) => (
  <select
    ref={ref}
    aria-invalid={invalid || undefined}
    className={cn(
      "flex h-10 w-full appearance-none rounded-md border border-input bg-background bg-[length:1rem] bg-no-repeat ps-3 pe-9 py-2 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50",
      invalid && "border-destructive focus-visible:ring-destructive",
      // `background-position` has no logical keyword, so the RTL edge is switched explicitly —
      // `pe-9` above already reserves the room on whichever side that turns out to be.
      "bg-[position:right_0.75rem_center] rtl:bg-[position:left_0.75rem_center]",
      className,
    )}
    style={{ backgroundImage: CHEVRON, ...style }}
    {...props}
  />
));
Select.displayName = "Select";
