import { describe, expect, it } from "vitest";

import { bidiIsolate, formatDate, formatNumber } from "./format";

describe("bidi-safe formatting (§9)", () => {
  it("wraps output in directional isolates so it can't reorder RTL text", () => {
    const out = bidiIsolate("123");
    expect(out.startsWith("⁨")).toBe(true); // FSI
    expect(out.endsWith("⁩")).toBe(true); // PDI
  });

  it("formats numbers and isolates them", () => {
    const out = formatNumber(1234, "en");
    expect(out).toContain("1,234");
    expect(out.startsWith("⁨")).toBe(true);
  });

  it("formats a date without throwing for every supported language", () => {
    const date = new Date("2026-07-22T00:00:00Z");
    for (const lang of ["en", "ar", "ckb"]) {
      expect(() => formatDate(date, lang)).not.toThrow();
    }
  });

  it("Kurdish falls back to Arabic Intl data (no crash, non-empty)", () => {
    const out = formatNumber(2026, "ckb");
    expect(out.length).toBeGreaterThan(0);
  });
});
