import { useCallback, useEffect, useRef, useState, type RefObject } from "react";

import type { Region } from "@/hooks/useCamera";

import {
  INITIAL_STATE,
  TUNING,
  cardBox,
  edgeScore,
  frameDelta,
  sharpness,
  step,
  toGrey,
  type AutoState,
  type Phase,
} from "./frameAnalysis";

// Sample sizes. The small one answers "is there a card, is it still" on ~6k pixels; the larger
// one measures focus, which needs enough pixels for the strokes of the text to exist at all.
const SMALL = { w: 96, h: 60 };
const FOCUS = { w: 320, h: 200 };

/** Watches the live video for a card held still inside the card-shaped box, and takes it.
 *
 * The loop is the dashboard's auto-scan idea (edge gate + steadiness), plus a focus check
 * because a soft card reads as nothing. `onCapture` receives the box region to crop; the caller
 * does the actual capture with the camera hook, so this stays a pure observer of pixels.
 */
export function useAutoCapture({
  videoRef,
  enabled,
  onCapture,
}: {
  videoRef: RefObject<HTMLVideoElement | null>;
  enabled: boolean;
  onCapture: (region: Region) => void;
}) {
  const [phase, setPhase] = useState<Phase>("searching");
  const stateRef = useRef<AutoState>(INITIAL_STATE);
  const previousRef = useRef<Float32Array | null>(null);
  const smallRef = useRef<HTMLCanvasElement | null>(null);
  const focusRef = useRef<HTMLCanvasElement | null>(null);
  const onCaptureRef = useRef(onCapture);
  onCaptureRef.current = onCapture;

  const reset = useCallback(() => {
    stateRef.current = INITIAL_STATE;
    previousRef.current = null;
    setPhase("searching");
  }, []);

  /** After a manual shot: hold the loop until the frame moves, exactly as after its own capture,
   * so the side just taken by hand is not taken again as the next one. */
  const lock = useCallback(() => {
    stateRef.current = { phase: "locked", stillSince: null };
    setPhase("locked");
  }, []);

  useEffect(() => {
    if (!enabled) {
      reset();
      return;
    }
    let cancelled = false;
    let timer = 0;

    const canvas = (ref: RefObject<HTMLCanvasElement | null>, w: number, h: number) => {
      if (!ref.current) {
        ref.current = document.createElement("canvas");
        ref.current.width = w;
        ref.current.height = h;
      }
      return ref.current.getContext("2d", { willReadFrequently: true });
    };

    // Draws the box region of the frame into a sample canvas and returns it as grey pixels.
    const sample = (ref: RefObject<HTMLCanvasElement | null>, size: { w: number; h: number }) => {
      const video = videoRef.current;
      const ctx = canvas(ref, size.w, size.h);
      if (!video || !ctx) return null;
      const box = cardBox(video.videoWidth, video.videoHeight);
      ctx.drawImage(
        video,
        box.x * video.videoWidth,
        box.y * video.videoHeight,
        box.w * video.videoWidth,
        box.h * video.videoHeight,
        0,
        0,
        size.w,
        size.h,
      );
      return toGrey(ctx.getImageData(0, 0, size.w, size.h).data);
    };

    const tick = () => {
      if (cancelled) return;
      const video = videoRef.current;
      if (video && video.videoWidth) {
        const small = sample(smallRef, SMALL);
        if (small) {
          const present = edgeScore(small, SMALL.w, SMALL.h) >= TUNING.edgeMin;
          const moved = previousRef.current
            ? frameDelta(small, previousRef.current) > TUNING.steadyMax
            : true;
          previousRef.current = small;
          // Focus is the expensive measure, so it is only taken once a still card is waiting on it.
          const needsFocus =
            present && !moved && stateRef.current.phase !== "locked" && stateRef.current.stillSince != null;
          const focus = needsFocus ? sample(focusRef, FOCUS) : null;
          const sharp = focus ? sharpness(focus, FOCUS.w, FOCUS.h) >= TUNING.sharpMin : false;

          const { next, capture } = step(stateRef.current, { present, moved, sharp }, performance.now());
          if (next.phase !== stateRef.current.phase) setPhase(next.phase);
          stateRef.current = next;
          if (capture) onCaptureRef.current(cardBox(video.videoWidth, video.videoHeight));
        }
      }
      timer = window.setTimeout(tick, TUNING.tickMs);
    };
    timer = window.setTimeout(tick, TUNING.tickMs);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [enabled, videoRef, reset]);

  return { phase, reset, lock };
}
