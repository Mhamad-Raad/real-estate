import { ArrowLeft } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";

import { useAppSelector } from "@/app/hooks";
import { Accordion, AccordionItem } from "@/components/ui/accordion";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/features/common/PageHeader";

import { useGetProcessQuery } from "../processesApi";
import type { OverallStatus, StepStatus } from "../types";
import { InstituteStepPanel } from "./InstituteStepPanel";
import { LawyerNotes } from "./LawyerNotes";
import { Step1Panel } from "./Step1Panel";
import { Step5Panel } from "./Step5Panel";
import { StepBadge } from "./StepBadge";

const OVERALL_VARIANT: Record<OverallStatus, BadgeProps["variant"]> = {
  draft: "neutral",
  in_progress: "default",
  complete: "success",
  rejected: "danger",
};

export function ProcessDetailPage() {
  const { t } = useTranslation();
  const { id } = useParams();
  const processId = Number(id);
  const user = useAppSelector((s) => s.auth.user);
  const { data: process, isLoading, isError } = useGetProcessQuery(processId);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  if (isError || !process) {
    return (
      <div className="mx-auto max-w-4xl">
        <Card>
          <CardContent className="py-10 text-center text-muted-foreground">
            {t("common.loadError")}
          </CardContent>
        </Card>
      </div>
    );
  }

  const canEdit = Boolean(user?.is_admin || process.assigned_lawyer === user?.id);
  const summary = process.step_status_summary;
  const statusFor = (n: number): StepStatus => summary.steps[String(n)] ?? "not_started";

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <Link
        to="/processes"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4 rtl:rotate-180" />
        {t("workflow.backToList")}
      </Link>

      <PageHeader
        title={process.client_full_name}
        description={`${t("clients.pid")}: ${process.client_pid}`}
        action={
          <div className="flex items-center gap-2">
            <Badge variant={OVERALL_VARIANT[process.overall_status]}>
              {t(`processes.status.${process.overall_status}`)}
            </Badge>
            <span className="text-sm text-muted-foreground">
              {t("workflow.rollup", { done: summary.completed, total: summary.total })}
            </span>
          </div>
        }
      />

      <LawyerNotes process={process} canEdit={canEdit} />

      <Accordion>
        {[1, 2, 3, 4, 5].map((n) => (
          <AccordionItem
            key={n}
            defaultOpen={n === (process.current_step || 1)}
            title={t(`workflow.step${n}`)}
            meta={<StepBadge status={statusFor(n)} />}
          >
            {n === 1 && <Step1Panel process={process} canEdit={canEdit} />}
            {(n === 2 || n === 3 || n === 4) && (
              <InstituteStepPanel process={process} step={n} canEdit={canEdit} />
            )}
            {n === 5 && (
              <Step5Panel process={process} canEdit={canEdit} isAdmin={Boolean(user?.is_admin)} />
            )}
          </AccordionItem>
        ))}
      </Accordion>
    </div>
  );
}
