import { describe, expect, it } from "vitest";

import {
  CARD_ASPECT,
  INITIAL_STATE,
  cardBox,
  edgeScore,
  frameDelta,
  sharpness,
  step,
  toGrey,
  type Sample,
} from "./frameAnalysis";

const W = 32;
const H = 20;

/** A flat grey frame. */
const flat = (value = 128) => new Float32Array(W * H).fill(value);

/** Sharp vertical stripes — printed text, roughly. */
const stripes = (period = 4) => {
  const g = new Float32Array(W * H);
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) g[y * W + x] = x % period < period / 2 ? 30 : 220;
  return g;
};

/** The same stripes after a box blur — what a shaking hand produces. */
const blurred = (g: Float32Array) => {
  const out = new Float32Array(W * H);
  for (let y = 0; y < H; y++)
    for (let x = 0; x < W; x++) {
      let sum = 0;
      let n = 0;
      for (let dy = -2; dy <= 2; dy++)
        for (let dx = -2; dx <= 2; dx++) {
          const yy = y + dy;
          const xx = x + dx;
          if (yy >= 0 && yy < H && xx >= 0 && xx < W) {
            sum += g[yy * W + xx];
            n++;
          }
        }
      out[y * W + x] = sum / n;
    }
  return out;
};

describe("cardBox", () => {
  it("is card-shaped and centred, as wide as the height cap allows", () => {
    // At 16:9 a card 80% wide would be 90% tall, so the 85% cap decides the width.
    const box = cardBox(1920, 1080);
    expect(box.h).toBeCloseTo(0.85);
    expect(box.w).toBeGreaterThan(0.7);
    expect((box.w * 1920) / (box.h * 1080)).toBeCloseTo(CARD_ASPECT);
    expect(box.x).toBeCloseTo((1 - box.w) / 2);
    expect(box.y).toBeCloseTo((1 - box.h) / 2);
  });

  it("takes the full 80% width when the frame is tall enough for it", () => {
    const box = cardBox(720, 1280);
    expect(box.w).toBeCloseTo(0.8);
    expect(box.y).toBeGreaterThanOrEqual(0);
    expect((box.w * 720) / (box.h * 1280)).toBeCloseTo(CARD_ASPECT);
  });
});

describe("frame measures", () => {
  it("converts RGBA to luma", () => {
    const grey = toGrey(new Uint8ClampedArray([255, 255, 255, 255, 0, 0, 0, 255]));
    expect(Array.from(grey)).toEqual([255, 0]);
  });

  it("sees texture in stripes and none on a bare desk", () => {
    expect(edgeScore(flat(), W, H)).toBe(0);
    expect(edgeScore(stripes(), W, H)).toBeGreaterThan(10);
  });

  it("reads a still frame as no change and a shifted one as motion", () => {
    expect(frameDelta(stripes(), stripes())).toBe(0);
    const shifted = new Float32Array(stripes().map((_, i, a) => a[(i + 2) % a.length]));
    expect(frameDelta(stripes(), shifted)).toBeGreaterThan(8);
    expect(frameDelta(flat(), new Float32Array(3))).toBe(Infinity);
  });

  it("ranks the sharp stripes far above their blurred copy", () => {
    const crisp = sharpness(stripes(), W, H);
    const soft = sharpness(blurred(stripes()), W, H);
    expect(crisp).toBeGreaterThan(60);
    expect(soft).toBeLessThan(crisp / 4);
  });
});

describe("step", () => {
  const still: Sample = { present: true, moved: false, sharp: true };
  const HOLD = 500;

  it("stays searching while the box is empty", () => {
    expect(step(INITIAL_STATE, { present: false, moved: true, sharp: false }, 0, HOLD)).toEqual({
      next: INITIAL_STATE,
      capture: false,
    });
  });

  it("captures once a sharp card has been still for the hold time", () => {
    const seen = step(INITIAL_STATE, still, 1000, HOLD);
    expect(seen.next).toEqual({ phase: "seen", stillSince: 1000 });
    expect(seen.capture).toBe(false);

    const early = step(seen.next, still, 1400, HOLD);
    expect(early.next.phase).toBe("seen");
    expect(early.capture).toBe(false);

    const done = step(early.next, still, 1500, HOLD);
    expect(done.capture).toBe(true);
    expect(done.next.phase).toBe("locked");
  });

  it("restarts the hold when the card moves", () => {
    const seen = step(INITIAL_STATE, still, 1000, HOLD);
    const moved = step(seen.next, { ...still, moved: true }, 1200, HOLD);
    expect(moved.next).toEqual({ phase: "seen", stillSince: null });
    const again = step(moved.next, still, 1300, HOLD);
    expect(again.next.stillSince).toBe(1300);
  });

  it("refuses a blurred card and takes it the moment it is sharp", () => {
    const seen = step(INITIAL_STATE, still, 0, HOLD);
    const soft = step(seen.next, { ...still, sharp: false }, 600, HOLD);
    expect(soft.next.phase).toBe("blurry");
    expect(soft.capture).toBe(false);
    const crisp = step(soft.next, still, 700, HOLD);
    expect(crisp.capture).toBe(true);
  });

  it("stays locked until the frame moves, however still and sharp the same side is", () => {
    const locked = { phase: "locked" as const, stillSince: null };
    expect(step(locked, still, 5000, HOLD)).toEqual({ next: locked, capture: false });
    expect(step(locked, { ...still, moved: true }, 5100, HOLD).next).toEqual(INITIAL_STATE);
  });
});
