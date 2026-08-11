import { Check, Minus } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Themed checkbox. Still a real `<input type="checkbox">` underneath — `appearance-none` plus our
 * own glyph — so native keyboard, form submission and screen-reader behaviour are all kept; a
 * `<div role="checkbox">` would have thrown those away.
 *
 * `accent-color` alone (what this replaced) only tints the OS control: its shape, border and check
 * glyph stay the platform's, so it looked foreign here and rendered differently on the office's
 * Windows hosts than in dev (§9, UC-018).
 */
export const Checkbox = React.forwardRef<
  HTMLInputElement,
  Omit<React.InputHTMLAttributes<HTMLInputElement>, "type"> & { indeterminate?: boolean }
>(({ className, indeterminate = false, checked, ...props }, ref) => {
  const inner = React.useRef<HTMLInputElement>(null);
  React.useImperativeHandle(ref, () => inner.current as HTMLInputElement);

  // `indeterminate` exists only as a DOM property — there is no attribute for it, so it cannot be
  // set through JSX. The select-all header needs it when only some rows are ticked.
  //
  // `checked` is in the deps because clicking a checkbox makes the browser clear `indeterminate`
  // on the element itself: if only `checked` changed, the effect would not re-run and the DOM
  // would keep the cleared value while the prop still said otherwise.
  React.useEffect(() => {
    if (inner.current) inner.current.indeterminate = indeterminate;
  }, [indeterminate, checked]);

  return (
    // `className` lands **here**, not on the input. Callers pass layout intent — a label that wraps
    // onto two lines nudges the box down with `mt-0.5` — and the glyph below is positioned against
    // this wrapper. Put on the input, the margin moved the box while the tick stayed, so the check
    // sat 2px high inside a 16px box: visibly off, and only on the checkboxes that pass a margin.
    <span className={cn("relative inline-flex size-4 shrink-0 align-middle", className)}>
      <input
        ref={inner}
        type="checkbox"
        checked={checked}
        className={cn(
          // Explicit 4px, not `rounded-sm`: this theme's --radius-sm is 6.4px, which on a 16px box
          // reads as a radio button — the wrong affordance for a multi-select control.
          "peer size-4 appearance-none rounded-[4px] border border-input bg-background shadow-sm transition-colors",
          "checked:border-primary checked:bg-primary indeterminate:border-primary indeterminate:bg-primary",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background",
          "disabled:cursor-not-allowed disabled:opacity-50",
        )}
        {...props}
      />
      {/* Symmetric glyphs, so nothing needs mirroring in RTL. */}
      <Check
        className="pointer-events-none absolute inset-0 hidden size-4 p-0.5 text-primary-foreground peer-checked:block peer-indeterminate:hidden"
        strokeWidth={3}
      />
      <Minus
        className="pointer-events-none absolute inset-0 hidden size-4 p-0.5 text-primary-foreground peer-indeterminate:block"
        strokeWidth={3}
      />
    </span>
  );
});
Checkbox.displayName = "Checkbox";
