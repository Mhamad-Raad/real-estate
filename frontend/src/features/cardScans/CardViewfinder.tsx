import { Camera, X } from "lucide-react";
import { useState, type RefObject } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { cardBox, type Phase } from "./frameAnalysis";

// The frame corners say what the loop sees: primary while searching, warning once a card is
// there, success the moment it is taken. Colour changes, never words alone — a lawyer watching
// the card, not the caption, still gets the message.
const CORNER: Record<Phase, string> = {
  searching: "border-primary/70",
  seen: "border-warning",
  blurry: "border-warning",
  locked: "border-success",
};

/** The live camera with a card-shaped guide, its status line, and the manual shutter. */
export function CardViewfinder({
  videoRef,
  phase,
  flash,
  target,
  onShoot,
  onCancel,
}: {
  videoRef: RefObject<HTMLVideoElement | null>;
  phase: Phase;
  /** Briefly true right after a capture — the green tint and the "taken" caption. */
  flash: boolean;
  /** Which side the next capture fills. */
  target: string;
  onShoot: () => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  // The overlay is laid out in fractions of the frame, so the element must be the frame's own
  // shape — otherwise the guide would not sit where the crop is taken from.
  const [aspect, setAspect] = useState(16 / 9);
  const box = cardBox(aspect, 1);
  const corner = flash ? CORNER.locked : CORNER[phase];

  const status = flash
    ? t("cardScan.auto.taken", { side: target })
    : t(`cardScan.auto.${phase === "locked" ? "searching" : phase}`, { side: target });

  return (
    <div className="space-y-2">
      <div
        className="relative w-full overflow-hidden rounded-md bg-black"
        style={{ aspectRatio: aspect }}
        data-phase={flash ? "taken" : phase}
      >
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="size-full object-contain"
          onLoadedMetadata={(e) => {
            const v = e.currentTarget;
            if (v.videoWidth && v.videoHeight) setAspect(v.videoWidth / v.videoHeight);
          }}
        />
        <div
          className="pointer-events-none absolute rounded-lg shadow-[0_0_0_9999px_rgba(0,0,0,0.35)]"
          style={{
            left: `${box.x * 100}%`,
            top: `${box.y * 100}%`,
            width: `${box.w * 100}%`,
            height: `${box.h * 100}%`,
          }}
        >
          {(["top-0 left-0 border-t-4 border-l-4 rounded-tl-lg",
            "top-0 right-0 border-t-4 border-r-4 rounded-tr-lg",
            "bottom-0 left-0 border-b-4 border-l-4 rounded-bl-lg",
            "bottom-0 right-0 border-b-4 border-r-4 rounded-br-lg"] as const).map((place) => (
            <span
              key={place}
              className={cn("absolute size-7 transition-colors duration-150", place, corner)}
            />
          ))}
        </div>
        {flash ? <div className="pointer-events-none absolute inset-0 bg-success/25" /> : null}
      </div>

      <p className="text-xs text-muted-foreground" role="status">
        {status}
      </p>

      <div className="flex flex-wrap gap-2">
        <Button type="button" size="sm" onClick={onShoot}>
          <Camera className="size-4" />
          {t("cardScan.shoot")}
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
          <X className="size-4" />
          {t("common.cancel")}
        </Button>
      </div>
    </div>
  );
}
