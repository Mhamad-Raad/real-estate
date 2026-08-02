import { ArrowDownRight, ArrowUpRight, type LucideIcon, Minus } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value?: number;
  hint?: string;
  icon: LucideIcon;
  loading?: boolean;
  /** Muted by default; `attention` marks a backlog figure worth acting on. */
  tone?: "default" | "attention";
  /** The same figure over the previous window; renders a comparison when supplied (UC-019). */
  previous?: number;
}

export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  loading,
  tone = "default",
  previous,
}: StatCardProps) {
  const { t, i18n } = useTranslation();
  const num = (n: number) => formatNumber(n, i18n.language);

  // "13 new cases" says nothing on its own; against the previous 30 days it says whether the
  // office is busier or quieter. Only rendered when the caller has a comparable earlier figure.
  const delta = previous === undefined || value === undefined ? null : value - previous;
  const DeltaIcon =
    delta === null || delta === 0 ? Minus : delta > 0 ? ArrowUpRight : ArrowDownRight;

  return (
    <Card>
      <CardContent className="space-y-3 p-4">
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm text-muted-foreground">{label}</p>
          <span
            className={cn(
              "flex size-8 shrink-0 items-center justify-center rounded-lg",
              tone === "attention"
                ? "bg-amber-500/10 text-amber-600 dark:text-amber-400"
                : "bg-primary/10 text-primary",
            )}
          >
            <Icon className="size-4" />
          </span>
        </div>

        {loading ? (
          <Skeleton className="h-9 w-20" />
        ) : (
          <div className="flex flex-wrap items-baseline gap-2">
            {/* The number is the point of the card, so it gets the line to itself. */}
            <p className="text-3xl font-semibold leading-none tabular-nums">{num(value ?? 0)}</p>
            {delta !== null && (
              <span
                className={cn(
                  "inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-xs font-medium",
                  // Tokens, never literal colours — a hard-coded hex breaks in dark mode (§9).
                  delta > 0 ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground",
                )}
              >
                {/* Directional, not textual: this arrow must NOT mirror in RTL. */}
                <DeltaIcon className="size-3" />
                {num(Math.abs(delta))}
              </span>
            )}
          </div>
        )}

        {(hint || delta !== null) && (
          <p className="text-xs text-muted-foreground">{hint ?? t("dashboard.vsPrevious")}</p>
        )}
      </CardContent>
    </Card>
  );
}
