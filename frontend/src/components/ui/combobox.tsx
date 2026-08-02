import { Check, ChevronDown } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

import { Spinner } from "./spinner";

export type ComboboxOption = {
  value: string;
  label: string;
  /** Secondary text — a PID, a code — shown muted beside the label. */
  hint?: string;
};

// One input that searches and shows its own results, rather than a search box wired to a separate
// dropdown the user has to discover (UC-022). The caller owns `term` so the search can be debounced
// and run server-side; this component owns only what is on screen.
export function Combobox({
  id,
  options,
  value,
  onSelect,
  term,
  onTermChange,
  placeholder,
  loading = false,
  disabled = false,
  emptyLabel,
  truncatedLabel,
  required = false,
}: {
  id?: string;
  options: ComboboxOption[];
  value: string;
  onSelect: (value: string) => void;
  term: string;
  onTermChange: (term: string) => void;
  placeholder?: string;
  loading?: boolean;
  disabled?: boolean;
  emptyLabel: string;
  /** Shown when the server has more matches than were returned — see UC-023. */
  truncatedLabel?: string;
  required?: boolean;
}) {
  const [open, setOpen] = React.useState(false);
  const [active, setActive] = React.useState(0);
  const rootRef = React.useRef<HTMLDivElement>(null);
  const listId = id ? `${id}-listbox` : undefined;
  const selected = options.find((o) => o.value === value);

  // Closing must restore the chosen label, or the input is left showing a half-typed search for a
  // selection that is still active — the state mismatch the old two-control version also had.
  const close = React.useCallback(() => {
    setOpen(false);
    onTermChange(selected?.label ?? "");
  }, [onTermChange, selected?.label]);

  React.useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) close();
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open, close]);

  const pick = (option: ComboboxOption) => {
    onSelect(option.value);
    onTermChange(option.label);
    setOpen(false);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      const delta = e.key === "ArrowDown" ? 1 : -1;
      setActive((i) => (options.length ? (i + delta + options.length) % options.length : 0));
    } else if (e.key === "Enter") {
      if (open && options[active]) {
        e.preventDefault();
        pick(options[active]);
      }
    } else if (e.key === "Escape") {
      if (open) {
        e.preventDefault();
        close();
      }
    }
  };

  return (
    <div ref={rootRef} className="relative">
      <input
        id={id}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        autoComplete="off"
        disabled={disabled}
        required={required && !value}
        value={term}
        placeholder={placeholder}
        onChange={(e) => {
          onTermChange(e.target.value);
          setActive(0);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
        className="flex h-10 w-full rounded-md border border-input bg-background ps-3 pe-9 py-2 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50"
      />
      {/* end-anchored so it mirrors in RTL; pointer-events-none keeps the input clickable through it */}
      <span className="pointer-events-none absolute inset-y-0 end-3 flex items-center">
        {loading ? (
          <Spinner />
        ) : (
          <ChevronDown className="size-4 text-muted-foreground" />
        )}
      </span>

      {open && (
        <div className="absolute z-50 mt-1 max-h-64 w-full overflow-y-auto rounded-md border border-border bg-popover p-1 shadow-md">
          {options.length === 0 && !loading && (
            <p className="px-2 py-3 text-center text-sm text-muted-foreground">
              {emptyLabel}
            </p>
          )}
          <ul id={listId} role="listbox">
            {options.map((option, i) => (
              <li
                key={option.value}
                role="option"
                aria-selected={option.value === value}
                // pointerdown, not click: the outside-close listener fires first and would tear
                // the list down before a click ever landed.
                onPointerDown={(e) => {
                  e.preventDefault();
                  pick(option);
                }}
                onMouseEnter={() => setActive(i)}
                className={cn(
                  "flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-sm",
                  i === active && "bg-accent text-accent-foreground",
                )}
              >
                <Check
                  className={cn(
                    "size-4 shrink-0",
                    option.value === value ? "opacity-100" : "opacity-0",
                  )}
                />
                <span className="truncate text-start">{option.label}</span>
                {option.hint && (
                  <span className="ms-auto shrink-0 text-xs text-muted-foreground" dir="ltr">
                    {option.hint}
                  </span>
                )}
              </li>
            ))}
          </ul>
          {/* A truncated list must never look like the whole list (UC-023). */}
          {truncatedLabel && (
            <p className="border-t border-border px-2 py-1.5 text-xs text-muted-foreground">
              {truncatedLabel}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
