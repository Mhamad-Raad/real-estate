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

  it("renders Arabic-Indic digits for both RTL languages, matching the printed letters", () => {
    // Guards a real trap: plain `ar` resolves to Latin digits under modern CLDR, so screens
    // would disagree with the generated PDFs unless the numbering system is pinned.
    for (const lang of ["ckb", "ar"]) {
      const out = formatNumber(2026, lang);
      expect(out).toMatch(/[٠-٩]/);
      expect(out).not.toMatch(/[0-9]/);
    }
    expect(formatNumber(2026, "en")).toMatch(/[0-9]/);
    expect(formatNumber(2026, "en")).not.toMatch(/[٠-٩]/);
  });
});
