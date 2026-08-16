import { Download, Printer } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { useAppSelector } from "@/app/hooks";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/lib/toast";

import { downloadFile, fetchBlobUrl, fileUrlFor, type FileSource } from "./download";

// Inline PDF preview + print. The bytes need an auth header, so they are fetched as a blob and
// handed to the iframe as an object URL — a plain <iframe src> would come back 401.
//
// Takes a `source` rather than a document id: the Step-1 letter is no longer a Document (UC-075)
// but is still previewed and printed from the case, and duplicating this component for the sake
// of one differing URL is how two previews drift apart.
export function DocumentPreview({
  source,
  title,
}: {
  source: FileSource;
  title: string;
}) {
  const { t } = useTranslation();
  const token = useAppSelector((s) => s.auth.access);
  const [url, setUrl] = useState<string | null>(null);
  const frame = useRef<HTMLIFrameElement>(null);
  const href = fileUrlFor(source);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    fetchBlobUrl(href, token)
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
  }, [href, token, t]);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">{t("workflow.preview")}</p>
        <div className="flex items-center gap-2">
          {/* Without this the only download on the page is the PDF viewer's own, inside the
              iframe — and that names the file after the blob URL, so a signed case file
              arrives as `af85281c-….pdf` instead of the composed name (UC-058). */}
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={!url}
            onClick={() =>
              downloadFile(href, title, token).catch(() =>
                toast.error(t("workflow.downloadError")),
              )
            }
          >
            <Download className="size-4" />
            {t("common.download")}
          </Button>
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
