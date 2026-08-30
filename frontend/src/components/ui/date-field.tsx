import { CalendarDays, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { Calendar } from "@/components/ui/calendar";
import {
  EMPTY_PARTS,
  isBlank,
  parsePasted,
  segmentInput,
  segmentIsFinished,
  toIso,
  toParts,
  type DateParts,
} from "@/lib/date";
import { cn } from "@/lib/utils";

/**
 * A date box that reads **day / month / year** on every machine (UC-108).
 *
 * It replaces `<input type="date">`, which is not wrong so much as **not ours**: a native date
 * input takes its order from a setting outside the app — the browser's UI language in Chrome and
 * Edge, the Windows regional format in Firefox, the OS locale in Safari — so the office saw
 * month/day/year and nothing in this codebase could say otherwise. Worse, the setting has to be
 * found again on every machine the app is installed on, and it is invisible from inside the app
 * when it is wrong.
 *
 * Value in and out is ISO `YYYY-MM-DD` (or "" for empty), exactly as the native input gave it, so
 * this is a drop-in for the call sites.
 *
 * **It also closes UC-072 at the source.** A native date input reports a *valid* value while the
 * year is still being typed — 2026 arrives as 2, then 20, then 202 — which is how the year 2 came
 * to be saved. Here a change is emitted only when the three boxes name a real day, or when they
 * are all empty; a half-typed date simply is not a value yet.
 */
export function DateField({
  value,
  onChange,
  onBlur,
  id,
  disabled,
  invalid,
  required,
  className,
  "aria-describedby": describedBy,
}: {
  /** ISO `YYYY-MM-DD`, or "" when empty. */
  value: string;
  onChange: (iso: string) => void;
  /** Fired when focus leaves the whole field — segments, calendar button and all. */
  onBlur?: () => void;
  id?: string;
  disabled?: boolean;
  invalid?: boolean;
  required?: boolean;
  className?: string;
  "aria-describedby"?: string;
}) {
  const { t } = useTranslation();
  const [parts, setParts] = useState<DateParts>(() => toParts(value));
  const [open, setOpen] = useState(false);
  const wrapper = useRef<HTMLDivElement>(null);
  // What the parent last showed us. Compared rather than the raw prop so a save echoing the same
  // date back does not rebuild the boxes under the cursor (the UC-072 reset, one layer up).
  const shown = useRef(value);

  useEffect(() => {
    if (value === shown.current) return;
    shown.current = value;
    setParts(toParts(value));
  }, [value]);

  const emit = (next: DateParts) => {
    setParts(next);
    const iso = isBlank(next) ? "" : toIso(next);
    if (iso === null) return; // still being typed — the parent keeps what it has
    shown.current = iso;
    onChange(iso);
  };

  const focusSegment = (kind: keyof DateParts) =>
    wrapper.current?.querySelector<HTMLInputElement>(`[data-segment="${kind}"]`)?.focus();

  const segment = (kind: keyof DateParts, size: number, next?: keyof DateParts) => ({
    "data-segment": kind,
    // The caller's `id` lands on the day box, so a `<Label htmlFor>` still focuses the field when
    // clicked — and its text, not "Day", is what names the field to a screen reader. Only an
    // unlabelled field falls back to naming the box itself.
    id: kind === "day" ? id : undefined,
    "aria-label": kind === "day" && id ? undefined : t(`common.date.${kind}`),
    // On every box, not only the wrapper: the labelled one is what a test and a screen reader
    // both reach for when asking whether this field is the rejected one.
    "aria-invalid": invalid || undefined,
    value: parts[kind],
    disabled,
    required,
    inputMode: "numeric" as const,
    // The office types Arabic-Indic digits; `segmentInput` folds them, so `type=text` rather than
    // `number` — a number input rejects the keystroke before we ever see it.
    maxLength: size,
    placeholder: "-".repeat(size),
    className: cn(
      "bg-transparent text-center tabular-nums outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed",
      size === 4 ? "w-10" : "w-6",
    ),
    onChange: (event: React.ChangeEvent<HTMLInputElement>) => {
      const text = segmentInput(event.target.value, size);
      emit({ ...parts, [kind]: text });
      if (next && segmentIsFinished(kind, text)) focusSegment(next);
    },
    // A whole date pasted into any of the boxes fills all three — a native date input took one,
    // and without this "05/08/2026" would land in the day box as "05".
    onPaste: (event: React.ClipboardEvent<HTMLInputElement>) => {
      const pasted = parsePasted(event.clipboardData.getData("text"));
      if (!pasted) return;
      event.preventDefault();
      emit(pasted);
    },
    onKeyDown: (event: React.KeyboardEvent<HTMLInputElement>) => {
      // Backspace at the start of an empty box steps back, so a whole date can be erased without
      // reaching for the mouse.
      if (event.key === "Backspace" && !parts[kind]) {
        const previous = kind === "year" ? "month" : kind === "month" ? "day" : null;
        if (previous) {
          event.preventDefault();
          focusSegment(previous);
        }
      }
    },
  });

  const clear = () => {
    emit(EMPTY_PARTS);
    focusSegment("day");
  };

  return (
    <div
      ref={wrapper}
      className="relative"
      onBlur={(event) => {
        // Only when focus has left the field altogether — moving between the boxes, or into the
        // calendar, is not a blur. The calendar sits **inside** this element for exactly that
        // reason: rendered as a sibling, every click in it closed the popover it was clicking.
        if (event.currentTarget.contains(event.relatedTarget)) return;
        // A half-typed date on screen would claim to be stored. Put back what actually is.
        if (!isBlank(parts) && toIso(parts) === null) setParts(toParts(value));
        setOpen(false);
        onBlur?.();
      }}
      onKeyDown={(event) => {
        if (event.key !== "Escape" || !open) return;
        event.stopPropagation();
        setOpen(false);
        focusSegment("day");
      }}
    >
      <div
        role="group"
        aria-describedby={describedBy}
        aria-invalid={invalid || undefined}
        className={cn(
          "flex h-10 w-full items-center gap-2 rounded-md border border-input bg-background px-3 text-sm shadow-sm transition-colors focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-1 focus-within:ring-offset-background",
          invalid && "border-destructive focus-within:ring-destructive",
          disabled && "opacity-50",
          className,
        )}
      >
        {/* The date reads day → month → year left to right in **every** language: a date is an
            LTR run even inside Sorani text, and letting it mirror would print the year first.
            Scoped to the boxes so the buttons and the calendar still follow the page. */}
        <div dir="ltr" className="flex items-center gap-0.5">
          <input {...segment("day", 2, "month")} />
          <span aria-hidden className="text-muted-foreground">/</span>
          <input {...segment("month", 2, "year")} />
          <span aria-hidden className="text-muted-foreground">/</span>
          <input {...segment("year", 4)} />
        </div>
        <div className="ms-auto flex items-center">
          {!disabled && !isBlank(parts) && (
            <IconButton label={t("common.date.clear")} onClick={clear}>
              <X className="size-4" />
            </IconButton>
          )}
          <IconButton
            label={t("common.date.open")}
            disabled={disabled}
            expanded={open}
            onClick={() => setOpen((was) => !was)}
          >
            <CalendarDays className="size-4" />
          </IconButton>
        </div>
      </div>
      {open && (
        <div className="absolute z-50 mt-1 rounded-md border border-border bg-popover text-popover-foreground shadow-md">
          <Calendar
            value={value}
            onPick={(iso) => {
              emit(toParts(iso));
              setOpen(false);
              focusSegment("day");
            }}
          />
        </div>
      )}
    </div>
  );
}

function IconButton({
  label,
  onClick,
  disabled,
  expanded,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  expanded?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      tabIndex={-1}
      aria-label={label}
      aria-expanded={expanded}
      disabled={disabled}
      onClick={onClick}
      className="rounded-md p-1 text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed"
    >
      {children}
    </button>
  );
}
