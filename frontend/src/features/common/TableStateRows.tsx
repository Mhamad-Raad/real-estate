import { AlertCircle } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { TableCell, TableRow } from "@/components/ui/table";

// Renders the loading / error / empty states for a data table in one place (DRY across list pages).
// Returns null when there's data to show, so the caller just renders its rows after it.
export function TableStateRows({
  colSpan,
  isLoading,
  isError,
  isEmpty,
  emptyLabel,
  onRetry,
  skeletonRows = 3,
}: {
  colSpan: number;
  isLoading: boolean;
  isError: boolean;
  isEmpty: boolean;
  emptyLabel: string;
  onRetry?: () => void;
  skeletonRows?: number;
}) {
  const { t } = useTranslation();

  if (isLoading) {
    return (
      <>
        {Array.from({ length: skeletonRows }).map((_, i) => (
          <TableRow key={i}>
            <TableCell colSpan={colSpan}>
              <Skeleton className="h-6 w-full" />
            </TableCell>
          </TableRow>
        ))}
      </>
    );
  }

  if (isError) {
    return (
      <TableRow>
        <TableCell colSpan={colSpan} className="py-10 text-center">
          <div className="flex flex-col items-center gap-3 text-muted-foreground">
            <AlertCircle className="size-6 text-destructive" />
            <span>{t("common.loadError")}</span>
            {onRetry && (
              <Button variant="outline" size="sm" onClick={onRetry}>
                {t("common.retry")}
              </Button>
            )}
          </div>
        </TableCell>
      </TableRow>
    );
  }

  if (isEmpty) {
    return (
      <TableRow>
        <TableCell colSpan={colSpan} className="py-10 text-center text-muted-foreground">
          {emptyLabel}
        </TableCell>
      </TableRow>
    );
  }

  return null;
}
