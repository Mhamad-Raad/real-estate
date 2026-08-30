import { Camera, RotateCcw, Upload, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { toast } from "@/lib/toast";
import { useCamera } from "@/hooks/useCamera";

// A card side, held as a File so the camera and the file picker produce the same thing and the
// upload code never has to know which one it came from.
export type CardSide = { file: File; url: string };

/** Stands in for a card the browser cannot draw — names the file, so it reads as attached. */
function Attached({ name, note }: { name: string; note: string }) {
  return (
    <div className="p-6 text-center text-xs text-muted-foreground">
      <p className="font-medium text-foreground">{name}</p>
      <p className="mt-1">{note}</p>
    </div>
  );
}

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
  // A TIFF is a **readable** card — the server converts it (§6.7) — but no browser can decode one
  // in an `<img>`, so the office's scanner output rendered as a broken icon and looked like the
  // file had not attached at all (UC-087). Only the tag knows: this is set from its own error.
  const [undecodable, setUndecodable] = useState(false);
  useEffect(() => setUndecodable(false), [side?.url]);

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
              <Attached name={side.file.name} note={t("cardScan.noPreview")} />
            </object>
          ) : undecodable ? (
            // Says the card IS attached. A blank box would send the lawyer looking for a fault
            // that is not there — the reading works on a file the browser cannot draw.
            <Attached name={side.file.name} note={t("cardScan.noPreview")} />
          ) : (
            <img
              src={side.url}
              alt={label}
              className="max-h-56 w-full object-contain"
              onError={() => setUndecodable(true)}
            />
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
        {/* Exactly what the server can read (`documents.filestore.IMAGE_MAGIC` + PDF). `image/*`
            also offered WebP, GIF and the iPhone's HEIC, which preview happily and are then
            refused on Read as "not a readable PDF" — a format offered here must work (UC-087). */}
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,image/jpeg,image/png,image/tiff"
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
