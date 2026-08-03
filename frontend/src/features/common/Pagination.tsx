import { ChevronLeft, ChevronRight } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { useNum } from "@/hooks/useNum";
import { PAGE_SIZE } from "@/services/types";

// Reusable pager driven by the DRF `count`. Hidden when everything fits on one page. Chevrons are
// logical (they mirror correctly in RTL because the row itself flips).
export function Pagination({
  page,
  count,
  onPage,
  pageSize = PAGE_SIZE,
}: {
  page: number;
  count: number;
  onPage: (page: number) => void;
  pageSize?: number;
}) {
  const { t } = useTranslation();
  const num = useNum();
  const pages = Math.max(1, Math.ceil(count / pageSize));
  if (pages <= 1) return null;

  return (
    <div className="flex items-center justify-between gap-3 text-sm text-muted-foreground">
      <span>{t("common.pageOf", { page: num(page), pages: num(pages) })}</span>
      <div className="flex gap-2">
        <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          <ChevronLeft className="size-4 rtl:rotate-180" />
          {t("common.prev")}
        </Button>
        <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          {t("common.next")}
          <ChevronRight className="size-4 rtl:rotate-180" />
        </Button>
      </div>
    </div>
  );
}
