import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { intlLocale } from "@/lib/format";
import { monthGrid, pad, shiftMonth, toParts, MAX_YEAR, MIN_YEAR } from "@/lib/date";
import { cn } from "@/lib/utils";

// Hand-built like Dialog, Select and Accordion (§8): the app is fully offline, and a date picker
// is not worth a dependency when the arithmetic already lives in `lib/date.ts`.

// Which day a week starts on. Not read from `Intl`: `getWeekInfo` is not available everywhere this
// has to run, and the office's answer is a fixed one — Saturday in Kurdistan, Sunday for the
// English interface.
const WEEK_START: Record<string, number> = { ckb: 6, ar: 6, en: 0 };

// Any Sunday; only the weekday matters. Used to name the seven column headings in the UI language.
const A_SUNDAY = Date.UTC(2026, 0, 4);

export function Calendar({
  value,
  onPick,
  className,
}: {
  /** The selected day as ISO `YYYY-MM-DD`, or "" when nothing is chosen yet. */
  value: string;
  onPick: (iso: string) => void;
  className?: string;
}) {
  const { t, i18n } = useTranslation();
  const locale = intlLocale(i18n.language);
  const weekStart = WEEK_START[i18n.language] ?? 0;

  const selected = toParts(value);
  const today = new Date();
  // Opens on the month being edited, or on this one when the field is empty.
  const [view, setView] = useState(() => ({
    year: Number(selected.year) || today.getFullYear(),
    month: Number(selected.month) || today.getMonth() + 1,
  }));
  // The day the arrow keys are on. Focus follows it, so the grid is one tab stop and not thirty.
  const [cursor, setCursor] = useState(() => Number(selected.day) || 1);
  const gridRef = useRef<HTMLDivElement>(null);
  const moved = useRef(false);

  // Only after a key moves it — focusing on first render would steal the caret out of the box the
  // office is still typing in.
  useEffect(() => {
    if (!moved.current) return;
    gridRef.current?.querySelector<HTMLButtonElement>(`[data-day="${cursor}"]`)?.focus();
  }, [cursor, view]);

  const iso = (day: number) => `${view.year}-${pad(view.month)}-${pad(day)}`;
  const step = (by: number) => {
    const shifted = shiftMonth(view.year, view.month, by);
    if (shifted.year < MIN_YEAR || shifted.year > MAX_YEAR) return;
    // Cleared, or the effect below would pull focus off the chevron and into the grid — so a
    // second click on "previous month" would have nothing under the pointer to press.
    moved.current = false;
    setView(shifted);
  };

  // Arrows walk the grid; crossing an edge turns the page, which is what makes the picker usable
  // for a birth date decades back without thirty clicks on the chevron.
  const walk = (by: number) => {
    const target = cursor + by;
    const grid = monthGrid(view.year, view.month, weekStart);
    const days = grid.flat().filter((d): d is number => d !== null).length;
    moved.current = true;
    if (target >= 1 && target <= days) return setCursor(target);
    const shifted = shiftMonth(view.year, view.month, target < 1 ? -1 : 1);
    if (shifted.year < MIN_YEAR || shifted.year > MAX_YEAR) return;
    const inNext = monthGrid(shifted.year, shifted.month, weekStart).flat().filter(Boolean).length;
    setView(shifted);
    setCursor(target < 1 ? inNext + target : target - days);
  };

  const onKeyDown = (event: React.KeyboardEvent) => {
    // Named by where they point on screen, not by "next": in RTL the left arrow means later.
    const back = i18n.dir() === "rtl" ? "ArrowRight" : "ArrowLeft";
    const forward = i18n.dir() === "rtl" ? "ArrowLeft" : "ArrowRight";
    const by = { [back]: -1, [forward]: 1, ArrowUp: -7, ArrowDown: 7 }[event.key];
    if (by === undefined) return;
    event.preventDefault();
    walk(by);
  };

  const weekdays = Array.from({ length: 7 }, (_, i) =>
    new Intl.DateTimeFormat(locale, { weekday: "narrow", timeZone: "UTC" }).format(
      A_SUNDAY + ((weekStart + i) % 7) * 86_400_000,
    ),
  );
  const digits = new Intl.NumberFormat(locale);
  const heading = new Intl.DateTimeFormat(locale, {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(Date.UTC(view.year, view.month - 1, 1));

  return (
    <div className={cn("w-64 select-none p-2", className)} onKeyDown={onKeyDown}>
      <div className="mb-2 flex items-center justify-between gap-1">
        <NavButton label={t("common.date.previousMonth")} onClick={() => step(-1)}>
          <ChevronLeft className="size-4 rtl:rotate-180" />
        </NavButton>
        <span className="text-sm font-medium">{heading}</span>
        <NavButton label={t("common.date.nextMonth")} onClick={() => step(1)}>
          <ChevronRight className="size-4 rtl:rotate-180" />
        </NavButton>
      </div>
      <div className="grid grid-cols-7 text-center text-xs text-muted-foreground">
        {weekdays.map((day, i) => (
          <span key={i} className="py-1">
            {day}
          </span>
        ))}
      </div>
      <div ref={gridRef} className="grid grid-cols-7 gap-0.5" role="grid">
        {monthGrid(view.year, view.month, weekStart)
          .flat()
          .map((day, i) =>
            day === null ? (
              <span key={i} />
            ) : (
              <button
                key={i}
                type="button"
                data-day={day}
                // One tab stop for the whole grid — the arrows move within it.
                tabIndex={day === cursor ? 0 : -1}
                aria-selected={iso(day) === value}
                onClick={() => onPick(iso(day))}
                className={cn(
                  "rounded-md py-1.5 text-sm transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  iso(day) === value && "bg-primary text-primary-foreground hover:bg-primary",
                  iso(day) !== value && isToday(view, day, today) && "font-bold text-primary",
                )}
              >
                {digits.format(day)}
              </button>
            ),
          )}
      </div>
    </div>
  );
}

function isToday(view: { year: number; month: number }, day: number, today: Date): boolean {
  return (
    view.year === today.getFullYear() &&
    view.month === today.getMonth() + 1 &&
    day === today.getDate()
  );
}

function NavButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {children}
    </button>
  );
}
