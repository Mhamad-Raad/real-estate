import { ArrowLeft, RotateCcw } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Accordion, AccordionItem } from "@/components/ui/accordion";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toaster";
import { useMeQuery } from "@/features/auth/authApi";
import { PageHeader } from "@/features/common/PageHeader";
import { useNum } from "@/hooks/useNum";
import { apiErrorMessage, apiErrorStatus } from "@/lib/apiError";

import { useCreateProcessMutation, useGetProcessQuery } from "../processesApi";
import type { OverallStatus, StepStatus } from "../types";
import { CompiledCasePanel } from "./CompiledCasePanel";
import { InstituteStepPanel } from "./InstituteStepPanel";
import { LawyerNotes } from "./LawyerNotes";
import { Step1Panel } from "./Step1Panel";
import { Step5Panel } from "./Step5Panel";
import { StepBadge } from "./StepBadge";
import { StepProceedBar } from "./StepProceedBar";

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
  // Read the warm /me cache, not the auth slice: ProtectedRoute hydrates the slice in an effect,
  // so on a deep link it lags a render and would briefly show an admin their steps as locked.
  const { data: user } = useMeQuery();
  const { data: process, isLoading, isError } = useGetProcessQuery(processId);
  const navigate = useNavigate();
  const num = useNum();
  const [createProcess, { isLoading: reapplying }] = useCreateProcessMutation();

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

  const isAdmin = Boolean(user?.is_admin);
  const canEdit = Boolean(isAdmin || process.assigned_lawyer === user?.id);
  const summary = process.step_status_summary;
  const statusFor = (n: number): StepStatus => summary.steps[String(n)] ?? "not_started";
  // Lawyers walk the steps one at a time — `current_step` is the highest one they've unlocked
  // via Proceed. Admins get the whole case at once for oversight (§5.2).
  const unlockedThrough = isAdmin ? 5 : Math.max(1, process.current_step);
  const missingFor = (n: number): string[] =>
    process.steps.find((s) => s.step_number === n)?.missing ?? [];

  // Opens a fresh case for the same beneficiary. The server allows it only because the previous
  // one is rejected; anything else comes back 409, which is the guarantee doing its job.
  const reapply = async () => {
    try {
      const created = await createProcess({ client: process.client }).unwrap();
      toast.success(t("processes.created"));
      navigate(`/processes/${created.id}`);
    } catch (err) {
      toast.error(
        apiErrorStatus(err) === 409
          ? t("processes.duplicateAllocation")
          : apiErrorMessage(err, t("common.saveError")),
      );
    }
  };

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
              {t("workflow.rollup", { done: num(summary.completed), total: num(summary.total) })}
            </span>
          </div>
        }
      />

      {/* A rejected applicant may apply again — `ix_process_active_alloc` excludes rejected
          precisely so they can (§3.7). Offered here rather than as a client picker on the intake
          form: you re-apply a *case*, you do not re-pick a *person* (UC-028). */}
      {process.overall_status === "rejected" && canEdit && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-muted/40 px-3 py-2.5 text-sm">
          <span className="text-muted-foreground">{t("workflow.reapplyNote")}</span>
          <Button size="sm" variant="outline" onClick={reapply} disabled={reapplying}>
            {reapplying ? <Spinner /> : <RotateCcw className="size-4 rtl:-scale-x-100" />}
            {t("workflow.reapply")}
          </Button>
        </div>
      )}

      <LawyerNotes process={process} canEdit={canEdit} />

      <Accordion>
        {[1, 2, 3, 4, 5].map((n) => {
          const locked = n > unlockedThrough;
          return (
            <AccordionItem
              key={n}
              locked={locked}
              defaultOpen={n === (process.current_step || 1)}
              title={t(`workflow.step${n}`)}
              meta={
                locked ? (
                  <span className="text-xs text-muted-foreground">{t("workflow.locked")}</span>
                ) : (
                  <StepBadge status={statusFor(n)} />
                )
              }
            >
              {n === 1 && <Step1Panel process={process} canEdit={canEdit} />}
              {(n === 2 || n === 3 || n === 4) && (
                <InstituteStepPanel process={process} step={n} canEdit={canEdit} />
              )}
              {n === 5 && (
                <div className="space-y-4">
                  <Step5Panel process={process} canEdit={canEdit} isAdmin={isAdmin} />
                  <CompiledCasePanel
                    processId={process.id}
                    documents={process.documents}
                    canGenerate={canEdit}
                  />
                </div>
              )}
              {n === process.current_step && n < 5 && canEdit && (
                <StepProceedBar process={process} step={n} missing={missingFor(n)} />
              )}
            </AccordionItem>
          );
        })}
      </Accordion>
    </div>
  );
}
