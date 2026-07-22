import { describe, expect, it } from "vitest";

import ar from "./locales/ar.json";
import ckb from "./locales/ckb.json";
import en from "./locales/en.json";
import { dirFor } from ".";

// Flatten a nested translation object to a sorted list of dotted key paths.
function flatKeys(obj: Record<string, unknown>, prefix = ""): string[] {
  return Object.entries(obj)
    .flatMap(([k, v]) => {
      const path = prefix ? `${prefix}.${k}` : k;
      return typeof v === "object" && v !== null
        ? flatKeys(v as Record<string, unknown>, path)
        : [path];
    })
    .sort();
}

describe("localization completeness (top-priority invariant §9)", () => {
  const enKeys = flatKeys(en);

  it("Arabic has exactly the same keys as English", () => {
    expect(flatKeys(ar)).toEqual(enKeys);
  });

  it("Kurdish (Sorani) has exactly the same keys as English", () => {
    expect(flatKeys(ckb)).toEqual(enKeys);
  });

  it("no translation value is empty", () => {
    for (const locale of [en, ar, ckb]) {
      const empties = flatKeys(locale).filter((key) => {
        const value = key
          .split(".")
          .reduce<unknown>((acc, part) => (acc as Record<string, unknown>)[part], locale);
        return typeof value === "string" && value.trim() === "";
      });
      expect(empties).toEqual([]);
    }
  });
});

describe("text direction", () => {
  it("Arabic-script languages are RTL, English is LTR", () => {
    expect(dirFor("ckb")).toBe("rtl");
    expect(dirFor("ar")).toBe("rtl");
    expect(dirFor("en")).toBe("ltr");
  });
});
