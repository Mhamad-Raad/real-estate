import { Check } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * One selectable preference — mode, palette or typeface. A real radio inside a label rather than
 * a clickable div: the group is single-select, so screen readers announce it correctly and arrow
 * keys move through it for free. The input is visually hidden; the card is the control.
 */
export function OptionCard({
  name,
  value,
  selected,
  onSelect,
  title,
  description,
  icon,
  children,
}: {
  name: string;
  value: string;
  selected: boolean;
  onSelect: () => void;
  title: string;
  description: string;
  icon?: ReactNode;
  children: ReactNode;
}) {
  return (
    <label
      className={cn(
        "relative cursor-pointer overflow-hidden rounded-lg border bg-card transition-shadow",
        "hover:shadow-md has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring",
        selected ? "border-primary shadow-sm ring-2 ring-primary" : "hover:border-primary/40",
      )}
    >
      <input
        type="radio"
        name={name}
        value={value}
        checked={selected}
        onChange={onSelect}
        className="sr-only"
      />
      {selected && (
        <span className="absolute end-2 top-2 z-10 rounded-full bg-primary p-1 text-primary-foreground">
          <Check className="size-3.5" strokeWidth={3} />
        </span>
      )}
      <div className="flex items-center gap-3 p-3">
        {icon && (
          <span
            className={cn(
              "shrink-0 rounded-md p-2",
              selected ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground",
            )}
          >
            {icon}
          </span>
        )}
        {/* min-w-0 lets the long translated names truncate instead of stretching the grid. */}
        <div className="min-w-0 pe-6">
          <p className="truncate text-sm font-medium">{title}</p>
          <p className="truncate text-xs text-muted-foreground">{description}</p>
        </div>
      </div>
      <div className="border-t">{children}</div>
    </label>
  );
}
