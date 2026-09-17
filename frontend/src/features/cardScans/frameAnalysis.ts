/** Pure frame arithmetic behind the card auto-capture (§6.1, UC-125).
 *
 * Everything here works on a small grey copy of the viewfinder box, so it is cheap enough to run
 * ten times a second and testable without a canvas. The camera hook owns the canvases; this
 * module only answers three questions about a sample — is a card there, is it still, is it
 * sharp — and decides what the capture loop does next.
 */

/** ID-1 card (85.6 × 53.98 mm), the format of the national ID. */
export const CARD_ASPECT = 85.6 / 53.98;

// Tuning — one place, so a webcam that behaves differently is fixed by numbers, not code.
export const TUNING = {
  /** Mean neighbour-pixel gradient (0–255) above which the box holds printed texture, not desk. */
  edgeMin: 10,
  /** Mean per-pixel change between samples below which the frame counts as still. */
  steadyMax: 8,
  /** Variance of the Laplacian below which the box is too soft to send. */
  sharpMin: 60,
  /** A still, sharp card must hold this long before it is taken — a hand settling is not a card. */
  holdMs: 500,
  /** How often the loop samples. Ten a second is plenty for a hand-held card and costs nothing. */
  tickMs: 100,
} as const;

export type Box = { x: number; y: number; w: number; h: number };

/** The card-shaped box, centred, as fractions of the frame: 80% of the width, never taller than
 * 85% of the height, so a portrait webcam still gets a card that fits. */
export function cardBox(frameW: number, frameH: number): Box {
  let w = 0.8;
  let h = (w * frameW) / CARD_ASPECT / frameH;
  if (h > 0.85) {
    h = 0.85;
    w = (h * frameH * CARD_ASPECT) / frameW;
  }
  return { x: (1 - w) / 2, y: (1 - h) / 2, w, h };
}

/** RGBA pixels → one luma value per pixel. */
export function toGrey(rgba: Uint8ClampedArray): Float32Array {
  const grey = new Float32Array(rgba.length / 4);
  for (let i = 0, j = 0; i < rgba.length; i += 4, j++) {
    grey[j] = rgba[i] * 0.299 + rgba[i + 1] * 0.587 + rgba[i + 2] * 0.114;
  }
  return grey;
}

/** Mean absolute difference between horizontal and vertical neighbours — texture, not brightness. */
export function edgeScore(grey: Float32Array, w: number, h: number): number {
  let sum = 0;
  let n = 0;
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const k = y * w + x;
      if (x + 1 < w) {
        sum += Math.abs(grey[k] - grey[k + 1]);
        n++;
      }
      if (y + 1 < h) {
        sum += Math.abs(grey[k] - grey[k + w]);
        n++;
      }
    }
  }
  return n ? sum / n : 0;
}

/** Mean absolute change per pixel between two samples of the same size. */
export function frameDelta(a: Float32Array, b: Float32Array): number {
  if (a.length !== b.length || a.length === 0) return Infinity;
  let sum = 0;
  for (let i = 0; i < a.length; i++) sum += Math.abs(a[i] - b[i]);
  return sum / a.length;
}

/** Variance of the 4-neighbour Laplacian — the classic focus measure. Blur flattens it. */
export function sharpness(grey: Float32Array, w: number, h: number): number {
  const n = (w - 2) * (h - 2);
  if (n <= 0) return 0;
  const lap = new Float32Array(n);
  let mean = 0;
  for (let y = 1, i = 0; y < h - 1; y++) {
    for (let x = 1; x < w - 1; x++, i++) {
      const k = y * w + x;
      lap[i] = 4 * grey[k] - grey[k - 1] - grey[k + 1] - grey[k - w] - grey[k + w];
      mean += lap[i];
    }
  }
  mean /= n;
  let variance = 0;
  for (let i = 0; i < n; i++) variance += (lap[i] - mean) ** 2;
  return variance / n;
}

/** What one sample says about the box. `sharp` is only meaningful when the frame is still. */
export type Sample = { present: boolean; moved: boolean; sharp: boolean };

export type Phase =
  /** Nothing card-like in the box. */
  | "searching"
  /** A card is there — waiting for it to be held still long enough. */
  | "seen"
  /** Still, but too soft to read: hold steadier, or move closer. */
  | "blurry"
  /** Taken. Stays locked until the frame moves — the same side is never sent twice. */
  | "locked";

export type AutoState = { phase: Phase; stillSince: number | null };

export const INITIAL_STATE: AutoState = { phase: "searching", stillSince: null };

/** One tick of the capture loop. Pure: the caller does the capturing when `capture` is true. */
export function step(
  state: AutoState,
  sample: Sample,
  now: number,
  holdMs: number = TUNING.holdMs,
): { next: AutoState; capture: boolean } {
  // Only motion re-arms a locked loop. A time-based re-arm would take the same side again while
  // it is still lying in the frame — the lawyer flipping the card is the motion that re-arms.
  if (state.phase === "locked") {
    return { next: sample.moved ? INITIAL_STATE : state, capture: false };
  }
  if (!sample.present) return { next: INITIAL_STATE, capture: false };
  if (sample.moved) return { next: { phase: "seen", stillSince: null }, capture: false };

  const stillSince = state.stillSince ?? now;
  if (now - stillSince < holdMs) return { next: { phase: "seen", stillSince }, capture: false };
  if (!sample.sharp) return { next: { phase: "blurry", stillSince }, capture: false };
  return { next: { phase: "locked", stillSince: null }, capture: true };
}
