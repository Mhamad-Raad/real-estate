import { Maximize2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { useAppSelector } from "@/app/hooks";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/lib/toast";
import { fetchBlobUrl } from "@/features/documents/download";

/**
 * One staged card, shown beside the fields read from it. Each person's card sits beside their own
 * fields, so the beneficiary's and the spouse's are never compared against the wrong scan (UC-128).
 *
 * This image is also the archived government record, so it has to be judged for legibility and
 * not merely read: "open full size" exists for that (UC-029).
 */
export function CardPreview({ scanId }: { scanId: number }) {
  const { t } = useTranslation();
  const token = useAppSelector((s) => s.auth.access);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  // The staged PDF needs the auth header, so a plain <iframe src> would come back 401.
  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    setPreviewUrl(null);

    fetchBlobUrl(`/api/v1/card-scans/${scanId}/file/`, token)
      .then(({ objectUrl: created }) => {
        if (cancelled) {
          URL.revokeObjectURL(created);
          return;
        }
        objectUrl = created;
        setPreviewUrl(created);
      })
      .catch(() => toast.error(t("cardScan.previewError")));

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl); // never leak the blob
    };
  }, [scanId, token, t]);

  return (
    // Sticky, because the fields pane is the longer of the two and the whole point is comparing
    // them — a scan that scrolls out of view cannot be compared.
    <div className="space-y-2 lg:sticky lg:top-4 lg:self-start">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">{t("cardScan.scannedCard")}</p>
        {previewUrl && (
          <a
            href={previewUrl}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
          >
            <Maximize2 className="size-3.5" />
            {t("cardScan.openFullSize")}
          </a>
        )}
      </div>
      {previewUrl ? (
        <iframe
          src={previewUrl}
          title={t("cardScan.scannedCard")}
          className="h-[36rem] w-full rounded-md border border-border bg-white"
        />
      ) : (
        <div className="flex h-[36rem] items-center justify-center rounded-md border border-border">
          <Spinner />
        </div>
      )}
      <p className="text-xs text-muted-foreground">{t("cardScan.qualityHint")}</p>
    </div>
  );
}
