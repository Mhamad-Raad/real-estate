import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/lib/toast";
import type { GenerationJob } from "@/features/documents/generationApi";
import { useGenerationRun } from "@/features/documents/useGenerationRun";
import { apiErrorMessage } from "@/lib/apiError";

interface GeneratedDocumentPanelProps {
  icon: LucideIcon;
  title: string;
  /** Shown under the title; omitted by panels that have nothing to add. */
  hint?: ReactNode;
  /** False hides the button entirely — the user may not generate on this case. */
  canGenerate: boolean;
  /** False disables the button and shows `locked` instead of `empty`. */
  unlocked: boolean;
  /** Whether there is already an output — drives regenerate-vs-generate and the empty text. */
  hasResult: boolean;
  labels: {
    generate: string;
    regenerate: string;
    busy: string;
    /** Confirms the job was queued. */
    started: string;
    failed: string;
    empty: string;
    locked: string;
  };
  onStart: () => Promise<GenerationJob>;
  /** What this panel does with a finished job — the two outputs land in different places. */
  onFinished: (job: GenerationJob) => void;
  starting: boolean;
  /** The finished output, rendered by the panel that knows what shape it takes. */
  children?: ReactNode;
}

/**
 * Shared shell for every "the system produced this PDF" panel (§6.6, §10.3).
 *
 * What is common is the *chrome and the run*: the button, its three labels, and the
 * poll-until-settled dance. What the output **is** differs — the compiled case is filed on the
 * process, the Step-1 letter is a standalone job file (UC-075) — so each panel renders its own
 * result and says what finishing means for it.
 */
export function GeneratedDocumentPanel({
  icon: Icon,
  title,
  hint,
  canGenerate,
  unlocked,
  hasResult,
  labels,
  onStart,
  onFinished,
  starting,
  children,
}: GeneratedDocumentPanelProps) {
  const { start, busy: running } = useGenerationRun(onFinished);
  const busy = starting || running;

  const run = async () => {
    try {
      const job = await onStart();
      start(job.id);
      // Rendering runs in the worker, so confirm the request landed before the file exists.
      toast.success(labels.started);
    } catch (err) {
      toast.error(apiErrorMessage(err, labels.failed));
    }
  };

  return (
    <div className="space-y-2 rounded-md border border-border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-2 text-sm font-medium">
          <Icon className="size-4 text-muted-foreground" />
          {title}
        </p>
        {canGenerate && (
          <Button
            size="sm"
            onClick={run}
            disabled={busy || !unlocked}
            title={unlocked ? undefined : labels.locked}
          >
            {busy && <Spinner />}
            {busy ? labels.busy : hasResult ? labels.regenerate : labels.generate}
          </Button>
        )}
      </div>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}

      {hasResult ? (
        children
      ) : (
        <p className="text-xs text-muted-foreground">{unlocked ? labels.empty : labels.locked}</p>
      )}
    </div>
  );
}
