import { Camera, RotateCcw, Upload, X } from "lucide-react";
import { useRef } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { toast } from "@/lib/toast";
import { useCamera } from "@/hooks/useCamera";

// A card side, held as a File so the camera and the file picker produce the same thing and the
// upload code never has to know which one it came from.
export type CardSide = { file: File; url: string };

/** Capture one side of the card — with the computer's camera, or from a file. */
export function CardCapture({
  label,
  hint,
  side,
  onChange,
  disabled = false,
}: {
  label: string;
  hint?: string;
  side: CardSide | null;
  onChange: (side: CardSide | null) => void;
  disabled?: boolean;
}) {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const camera = useCamera();

  const openCamera = async () => {
    if (!(await camera.open())) toast.error(t("cardScan.cameraDenied"));
  };

  const shoot = async () => {
    const file = await camera.capture(`${label}.jpg`);
    if (!file) return;
    replace({ file, url: URL.createObjectURL(file) });
    camera.stop();
  };

  // One object URL alive per side; the previous one is revoked so previews cannot leak.
  const replace = (next: CardSide | null) => {
    if (side) URL.revokeObjectURL(side.url);
    onChange(next);
  };

  const onFile = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) replace({ file, url: URL.createObjectURL(file) });
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-sm font-medium">{label}</p>
        {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
      </div>

      <div className="relative flex min-h-40 items-center justify-center overflow-hidden rounded-md border border-dashed border-border bg-muted/40">
        {side ? (
          // A PDF is not an image: `<img>` renders nothing for one, so an imported scan looked
          // like nothing had been picked at all (UC-070). The office imports PDFs routinely —
          // that is how their scanner delivers a card — so both shapes have to show.
          side.file.type === "application/pdf" ? (
            <object
              data={side.url}
              type="application/pdf"
              aria-label={label}
              className="h-56 w-full"
            >
              <p className="p-6 text-center text-xs text-muted-foreground">{side.file.name}</p>
            </object>
          ) : (
            <img src={side.url} alt={label} className="max-h-56 w-full object-contain" />
          )
        ) : camera.active ? (
          <video
            ref={camera.videoRef}
            autoPlay
            playsInline
            muted
            className="max-h-56 w-full object-contain"
          />
        ) : (
          <p className="p-6 text-center text-xs text-muted-foreground">{t("cardScan.noImage")}</p>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        <input
          ref={inputRef}
          type="file"
          accept="image/*,application/pdf"
          className="hidden"
          onChange={onFile}
        />
        {side ? (
          <Button type="button" variant="outline" size="sm" disabled={disabled} onClick={() => replace(null)}>
            <RotateCcw className="size-4" />
            {t("cardScan.retake")}
          </Button>
        ) : camera.active ? (
          <>
            <Button type="button" size="sm" disabled={disabled} onClick={shoot}>
              <Camera className="size-4" />
              {t("cardScan.shoot")}
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={camera.stop}>
              <X className="size-4" />
              {t("common.cancel")}
            </Button>
          </>
        ) : (
          <>
            <Button type="button" variant="outline" size="sm" disabled={disabled} onClick={openCamera}>
              <Camera className="size-4" />
              {t("cardScan.useCamera")}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={disabled}
              onClick={() => inputRef.current?.click()}
            >
              <Upload className="size-4" />
              {t("cardScan.chooseFile")}
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
