import { Download, Printer } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { useAppSelector } from "@/app/hooks";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/lib/toast";

import { fetchBlobUrl, fileUrlFor, saveBlobUrl, type FileSource } from "./download";

// Inline PDF preview + print. The bytes need an auth header, so they are fetched as a blob and
// handed to the iframe as an object URL — a plain <iframe src> would come back 401.
//
// Takes a `source` rather than a document id: the Step-1 letter is no longer a Document (UC-075)
// but is still previewed and printed from the case, and duplicating this component for the sake
// of one differing URL is how two previews drift apart.
type Fetched = { href: string; objectUrl: string; filename?: string };

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
  // Captured with the blob so downloading needs no second request (UC-102) — a generated letter is
  // deleted the moment it is read, so a re-fetch would find nothing there.
  const [serverName, setServerName] = useState<string | null>(null);
  const frame = useRef<HTMLIFrameElement>(null);
  const href = fileUrlFor(source);

  // **Read once per file, and never twice.** A generated letter is deleted by the read that serves
  // it (UC-102), so a second fetch of the same URL 404s and the screen reports a failure for a file
  // that arrived perfectly — which is how the office saw it.
  //
  // Two things are shared across effect runs, and both are needed. The **in-flight request**,
  // because StrictMode tears the effect down and re-runs it *before* the first fetch resolves, so a
  // result cache alone would still fire a second request. And the **result**, because a later
  // remount must not go back to a server that no longer has the file.
  const cached = useRef<Fetched | null>(null);
  const inflight = useRef<{ href: string; promise: Promise<Fetched> } | null>(null);
  const notify = useRef(t);
  notify.current = t;

  useEffect(() => {
    let cancelled = false;

    if (cached.current?.href === href) {
      setUrl(cached.current.objectUrl);
      setServerName(cached.current.filename ?? null);
      return;
    }
    if (inflight.current?.href !== href) {
      inflight.current = {
        href,
        promise: fetchBlobUrl(href, token).then(({ objectUrl, filename }) => ({
          href,
          objectUrl,
          filename,
        })),
      };
    }

    inflight.current.promise
      .then((result) => {
        // Cached even when this render was torn down: the teardown is StrictMode's, the file is
        // already spent, and discarding the bytes would strand the run that replaces us.
        cached.current = result;
        if (cancelled) return;
        setUrl(result.objectUrl);
        setServerName(result.filename ?? null);
      })
      // The server explains this one better than we can — it names regenerating as the fix.
      .catch((err: Error) =>
        toast.error(err?.message || notify.current("workflow.previewError")),
      );

    return () => {
      cancelled = true;
    };
  }, [href, token]);

  // Released when the panel closes for good — not on every effect re-run, which is what lets the
  // blob survive StrictMode's remount.
  useEffect(
    () => () => {
      if (cached.current) URL.revokeObjectURL(cached.current.objectUrl);
    },
    [],
  );

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
            onClick={() => {
              if (!url) return;
              saveBlobUrl(url, serverName ?? `${title}.pdf`);
            }}
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
