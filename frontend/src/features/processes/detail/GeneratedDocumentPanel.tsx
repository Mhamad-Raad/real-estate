import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { useAppDispatch } from "@/app/hooks";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/lib/toast";
import { DocumentPreview } from "@/features/documents/DocumentPreview";
import { DocumentRow } from "@/features/documents/DocumentRow";
import type { GenerationJob } from "@/features/documents/generationApi";
import { useGenerationRun } from "@/features/documents/useGenerationRun";
import type { DocumentMeta } from "@/features/documents/types";
import { apiErrorMessage } from "@/lib/apiError";
import { baseApi } from "@/services/baseApi";

interface GeneratedDocumentPanelProps {
  processId: number;
  /** The live documents this panel owns, newest first. */
  documents: DocumentMeta[];
  icon: LucideIcon;
  title: string;
  /** Shown under the title; omitted by panels that have nothing to add. */
  hint?: ReactNode;
  /** False hides the button entirely — the user may not generate on this case. */
  canGenerate: boolean;
  /** False disables the button and shows `lockedLabel` instead of `emptyLabel`. */
  unlocked: boolean;
  labels: {
    generate: string;
    regenerate: string;
    busy: string;
    /** Confirms the job was queued. */
    started: string;
    /** Confirms the finished file is attached. */
    done: string;
    failed: string;
    empty: string;
    locked: string;
  };
  onStart: () => Promise<GenerationJob>;
  starting: boolean;
}

/**
 * Shared shell for every "the system produced this PDF" panel (§6.6, §10.3).
 *
 * The eligibility letter and the compiled case differ only in their mutation, labels and unlock
 * rule — the poll-until-settled dance, cache invalidation, newest-first ordering, row list and
 * inline preview are identical, so they live here once.
 */
export function GeneratedDocumentPanel({
  processId,
  documents,
  icon: Icon,
  title,
  hint,
  canGenerate,
  unlocked,
  labels,
  onStart,
  starting,
}: GeneratedDocumentPanelProps) {
  const dispatch = useAppDispatch();
  const { start, busy: running } = useGenerationRun(() => {
    // The output is a new Document on the process — refetch the detail so it appears.
    dispatch(baseApi.util.invalidateTags([{ type: "Process", id: processId }]));
    toast.success(labels.done);
  });

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
            {busy ? labels.busy : documents.length ? labels.regenerate : labels.generate}
          </Button>
        )}
      </div>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}

      {documents.length ? (
        <div className="space-y-3">
          <div className="space-y-1">
            {documents.map((doc, i) => (
              // The newest is already previewed below, so it must not offer its own toggle —
              // that opened a second copy of the same PDF under the first (UC-069).
              <DocumentRow key={doc.id} doc={doc} previewable={i !== 0} />
            ))}
          </div>
          {/* Newest shown inline so it can be checked and printed without leaving the case. */}
          <DocumentPreview documentId={documents[0].id} title={documents[0].display_filename} />
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">
          {unlocked ? labels.empty : labels.locked}
        </p>
      )}
    </div>
  );
}

