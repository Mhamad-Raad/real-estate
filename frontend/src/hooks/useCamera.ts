import { useCallback, useEffect, useRef, useState } from "react";

/** The computer's own camera, as a capture source (§6.1).
 *
 * Shared by the ID-card capture and the multi-page document scanner: both open the same device,
 * draw the same frame to a canvas and hand back the same `File`, so the upload code downstream
 * never has to know whether a page came from the camera or from disk.
 */
export function useCamera() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);

  const stop = useCallback(() => {
    setStream((current) => {
      current?.getTracks().forEach((track) => track.stop());
      return null;
    });
  }, []);

  // The camera must be released on unmount, or its light stays on after the dialog closes.
  useEffect(() => stop, [stop]);

  useEffect(() => {
    if (stream && videoRef.current) videoRef.current.srcObject = stream;
  }, [stream]);

  /** Open the device. Returns false when the user or the OS refuses, so the caller can say so
   * in its own words rather than the hook guessing at the wording. */
  const open = useCallback(async () => {
    try {
      // The rear camera on a tablet; a laptop simply ignores the preference.
      const opened = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment", width: { ideal: 1920 } },
      });
      setStream(opened);
      return true;
    } catch {
      return false;
    }
  }, []);

  /** Grab the current frame as a JPEG file. */
  const capture = useCallback((filename: string) => {
    return new Promise<File | null>((resolve) => {
      const video = videoRef.current;
      if (!video) return resolve(null);
      const canvas = document.createElement("canvas");
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      canvas.getContext("2d")?.drawImage(video, 0, 0);
      // JPEG at high quality: OCR accuracy depends on resolution, and nothing downstream
      // resamples — the server wraps these pixels, and pdf-lib embeds them, untouched.
      canvas.toBlob(
        (blob) => resolve(blob ? new File([blob], filename, { type: "image/jpeg" }) : null),
        "image/jpeg",
        0.95,
      );
    });
  }, []);

  return { videoRef, active: stream !== null, open, stop, capture };
}
