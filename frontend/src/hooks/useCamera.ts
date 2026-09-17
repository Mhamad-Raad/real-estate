import { useCallback, useEffect, useRef, useState } from "react";

/** A region of the frame as fractions of its width and height. */
export type Region = { x: number; y: number; w: number; h: number };

/** The computer's own camera, as a capture source (§6.1).
 *
 * Shared by the ID-card capture and the multi-page document scanner: both open the same device,
 * draw the same frame to a canvas and hand back the same `File`, so the upload code downstream
 * never has to know whether a page came from the camera or from disk.
 */
export function useCamera() {
  const videoRef = useRef<HTMLVideoElement>(null);
  // Stream in a ref, presence in state: releasing a device is a side effect, banned in an updater.
  const streamRef = useRef<MediaStream | null>(null);
  const [active, setActive] = useState(false);

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setActive(false);
  }, []);

  // The camera must be released on unmount, or its light stays on after the dialog closes.
  useEffect(() => stop, [stop]);

  useEffect(() => {
    if (active && videoRef.current) videoRef.current.srcObject = streamRef.current;
  }, [active]);

  /** Open the device. Returns false when the user or the OS refuses, so the caller can say so
   * in its own words rather than the hook guessing at the wording. */
  const open = useCallback(async () => {
    try {
      // The rear camera on a tablet; a laptop or USB webcam simply ignores the preference. Full HD
      // is asked for because the card fills only part of the frame and the read needs the pixels.
      streamRef.current = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment", width: { ideal: 1920 }, height: { ideal: 1080 } },
      });
      setActive(true);
      return true;
    } catch {
      return false;
    }
  }, []);

  /** Grab the current frame — or just a region of it — as a JPEG file at the camera's own
   * resolution. Nothing is upscaled or filtered: the read works best on untouched pixels (§6.2). */
  const capture = useCallback((filename: string, region?: Region) => {
    return new Promise<File | null>((resolve) => {
      const video = videoRef.current;
      if (!video || !video.videoWidth) return resolve(null);
      const r = region ?? { x: 0, y: 0, w: 1, h: 1 };
      const sx = Math.round(r.x * video.videoWidth);
      const sy = Math.round(r.y * video.videoHeight);
      const sw = Math.round(r.w * video.videoWidth);
      const sh = Math.round(r.h * video.videoHeight);
      const canvas = document.createElement("canvas");
      canvas.width = sw;
      canvas.height = sh;
      canvas.getContext("2d")?.drawImage(video, sx, sy, sw, sh, 0, 0, sw, sh);
      // High quality: OCR needs the resolution, and nothing downstream resamples these pixels.
      canvas.toBlob(
        (blob) => resolve(blob ? new File([blob], filename, { type: "image/jpeg" }) : null),
        "image/jpeg",
        0.95,
      );
    });
  }, []);

  return { videoRef, active, open, stop, capture };
}
