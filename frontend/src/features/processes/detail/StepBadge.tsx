import { useTranslation } from "react-i18next";

import { Badge, type BadgeProps } from "@/components/ui/badge";
import type { StepStatus } from "../types";

// Maps a step's computed status to a colored badge (§5.4).
const VARIANT: Record<StepStatus, BadgeProps["variant"]> = {
  not_started: "neutral",
  in_progress: "warning",
  missing: "danger",
  complete: "success",
};

export function StepBadge({ status }: { status: StepStatus }) {
  const { t } = useTranslation();
  return <Badge variant={VARIANT[status]}>{t(`workflow.stepStatus.${status}`)}</Badge>;
}
