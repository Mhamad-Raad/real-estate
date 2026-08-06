import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { toast } from "@/lib/toast";

import {
  isSettled,
  useGetGenerationJobQuery,
  type GenerationJob,
} from "./generationApi";

// One place for the poll-until-settled dance both generate buttons need (§6.6, §6.8): start a
// job, poll while it runs, stop the moment it settles, and report a failure once.
export function useGenerationRun(onDone: (job: GenerationJob) => void) {
  const { t } = useTranslation();
  const [jobId, setJobId] = useState<number | null>(null);

  // Held in a ref so a caller's inline arrow function cannot restart the effect on every render.
  const handler = useRef(onDone);
  handler.current = onDone;

  const { data: job } = useGetGenerationJobQuery(jobId as number, {
    skip: jobId === null,
    pollingInterval: 1500,
  });

  useEffect(() => {
    if (!job || !isSettled(job.status)) return;
    setJobId(null); // settled — stop polling
    if (job.status === "done") {
      handler.current(job);
    } else {
      toast.error(job.error || t("workflow.generateFailed"));
    }
  }, [job, t]);

  return { start: setJobId, busy: jobId !== null };
}
