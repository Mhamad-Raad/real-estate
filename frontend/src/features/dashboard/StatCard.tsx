import type { LucideIcon } from "lucide-react";
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
}

export function StatCard({ label, value, hint, icon: Icon, loading, tone = "default" }: StatCardProps) {
  const { i18n } = useTranslation();

  return (
    <Card>
      <CardContent className="flex items-start gap-3 p-4">
        <span
          className={cn(
            "flex size-9 shrink-0 items-center justify-center rounded-lg",
            tone === "attention"
              ? "bg-amber-500/10 text-amber-600 dark:text-amber-400"
              : "bg-primary/10 text-primary",
          )}
        >
          <Icon className="size-4" />
        </span>
        <div className="min-w-0 space-y-1">
          <p className="text-sm text-muted-foreground">{label}</p>
          {loading ? (
            <Skeleton className="h-7 w-14" />
          ) : (
            <p className="text-2xl font-semibold tabular-nums">{formatNumber(value ?? 0, i18n.language)}</p>
          )}
          {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
        </div>
      </CardContent>
    </Card>
  );
}
