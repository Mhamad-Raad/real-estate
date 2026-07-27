import { Printer } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { useAppSelector } from "@/app/hooks";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toaster";

import { fetchDocumentBlobUrl } from "./download";

// Inline PDF preview + print. The bytes need an auth header, so they are fetched as a blob and
// handed to the iframe as an object URL — a plain <iframe src> would come back 401.
export function DocumentPreview({
  documentId,
  title,
}: {
  documentId: number;
  title: string;
}) {
  const { t } = useTranslation();
  const token = useAppSelector((s) => s.auth.access);
  const [url, setUrl] = useState<string | null>(null);
  const frame = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    fetchDocumentBlobUrl(documentId, token)
      .then((created) => {
        // The document may have changed (regenerated) while this was in flight.
        if (cancelled) {
          URL.revokeObjectURL(created);
          return;
        }
        objectUrl = created;
        setUrl(created);
      })
      .catch(() => toast.error(t("workflow.previewError")));

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl); // never leak the blob
    };
  }, [documentId, token, t]);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">{t("workflow.preview")}</p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!url}
          onClick={() => frame.current?.contentWindow?.print()}
        >
          <Printer className="size-4" />
          {t("workflow.print")}
        </Button>
      </div>

      {url ? (
        <iframe
          ref={frame}
          src={url}
          title={title}
          className="h-[28rem] w-full rounded-md border border-border bg-white"
        />
      ) : (
        <div className="flex h-24 items-center justify-center rounded-md border border-border">
          <Spinner />
        </div>
      )}
    </div>
  );
}
