import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { toast } from "@/lib/toast";

import { useGetCardScanQuery } from "./cardScansApi";
import { isSettled, type CardScan } from "./types";

// Poll a staged card until its reading settles, then stop (§6.3). Mirrors `useGenerationRun`:
// same shape, different job — but deliberately NOT merged with it, because a failed reading is
// not an error here. The scan stays staged and the lawyer types the fields in instead.
export function useCardReading(scanId: number | null, onDone: (scan: CardScan) => void) {
  const { t } = useTranslation();
  const [settledId, setSettledId] = useState<number | null>(null);

  // Held in a ref so a caller's inline arrow cannot restart the effect on every render.
  const handler = useRef(onDone);
  handler.current = onDone;

  const { data: scan } = useGetCardScanQuery(scanId as number, {
    skip: scanId === null,
    pollingInterval: scanId !== null && scanId !== settledId ? 1500 : 0,
  });

  useEffect(() => {
    if (!scan || !isSettled(scan.status) || scan.id === settledId) return;
    setSettledId(scan.id); // settled — stop polling
    handler.current(scan);
    if (scan.status === "done") {
      toast.success(t("cardScan.readingDone"));
    } else {
      // Not an error state: the card is still there to be typed in by hand.
      toast.info(t("cardScan.readingFailed"));
    }
  }, [scan, settledId, t]);

  return { scan, reading: scanId !== null && scanId !== settledId };
}
