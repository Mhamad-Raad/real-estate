import { Camera, RotateCcw, Upload, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/toaster";

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
  const videoRef = useRef<HTMLVideoElement>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);

  const stopCamera = useCallback(() => {
    setStream((current) => {
      current?.getTracks().forEach((track) => track.stop());
      return null;
    });
  }, []);

  // The camera must be released on unmount, or its light stays on after the dialog closes.
  useEffect(() => stopCamera, [stopCamera]);

  useEffect(() => {
    if (stream && videoRef.current) videoRef.current.srcObject = stream;
  }, [stream]);

  const openCamera = async () => {
    try {
      // The rear camera on a tablet; a laptop simply ignores the preference.
      const opened = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment", width: { ideal: 1920 } },
      });
      setStream(opened);
    } catch {
      toast.error(t("cardScan.cameraDenied"));
    }
  };

  const shoot = () => {
    const video = videoRef.current;
    if (!video) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d")?.drawImage(video, 0, 0);
    // JPEG at high quality: OCR accuracy depends on resolution, and the server does not resample.
    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        const file = new File([blob], `${label}.jpg`, { type: "image/jpeg" });
        replace({ file, url: URL.createObjectURL(blob) });
        stopCamera();
      },
      "image/jpeg",
      0.95,
    );
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
          <img src={side.url} alt={label} className="max-h-56 w-full object-contain" />
        ) : stream ? (
          <video ref={videoRef} autoPlay playsInline muted className="max-h-56 w-full object-contain" />
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
        ) : stream ? (
          <>
            <Button type="button" size="sm" disabled={disabled} onClick={shoot}>
              <Camera className="size-4" />
              {t("cardScan.shoot")}
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={stopCamera}>
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
