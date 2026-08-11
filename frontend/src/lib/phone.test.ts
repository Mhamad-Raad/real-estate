import { describe, expect, it } from "vitest";

import {
  PHONE_MAX_DIGITS,
  PHONE_MAX_DIGITS_WITH_COUNTRY_CODE,
  sanitisePhoneInput,
} from "./phone";

const digitsIn = (value: string) => (value.match(/[0-9٠-٩۰-۹]/g) ?? []).length;

describe("sanitisePhoneInput", () => {
  it("refuses letters outright — the reported complaint", () => {
    expect(sanitisePhoneInput("sajnasfnasfns")).toBe("");
    expect(sanitisePhoneInput("0770callme")).toBe("0770");
    // The spaces between the dropped words survive — a space is a legal separator, and hunting
    // stray ones down mid-type would rewrite the value under the user for no gain.
    expect(sanitisePhoneInput("0770 call me")).toBe("0770  ");
  });

  it("keeps the separators the office types", () => {
    expect(sanitisePhoneInput("0770 123 4567")).toBe("0770 123 4567");
    expect(sanitisePhoneInput("0770-123-4567")).toBe("0770-123-4567");
    expect(sanitisePhoneInput("(0770) 1234567")).toBe("(0770) 1234567");
  });

  it("keeps Arabic-Indic digits — the office writes numbers in them", () => {
    expect(sanitisePhoneInput("٠٧٧٠١٢٣٤٥٦٧")).toBe("٠٧٧٠١٢٣٤٥٦٧");
    expect(sanitisePhoneInput("۰۷۷۰۱۲۳۴۵۶۷")).toBe("۰۷۷۰۱۲۳۴۵۶۷");
  });

  it("stops at the longest Iraqi number instead of growing forever", () => {
    const typed = sanitisePhoneInput("077012345678888888");
    expect(digitsIn(typed)).toBe(PHONE_MAX_DIGITS);
    expect(typed).toBe("07701234567");
  });

  it("keeps what was typed first, dropping only the overflow", () => {
    // Truncating the *start* would silently rewrite a number the user was mid-way through.
    expect(sanitisePhoneInput("٠٧٧٠١٢٣٤٥٦٧٨٩")).toBe("٠٧٧٠١٢٣٤٥٦٧");
  });

  it("allows a country code its extra room", () => {
    expect(sanitisePhoneInput("+9647701234567")).toBe("+9647701234567");
    expect(digitsIn(sanitisePhoneInput("+96477012345679999"))).toBe(
      PHONE_MAX_DIGITS_WITH_COUNTRY_CODE,
    );
  });

  it("treats `+` as meaningful only at the front", () => {
    expect(sanitisePhoneInput("0770+123")).toBe("0770123");
    expect(sanitisePhoneInput("+964+770")).toBe("+964770");
  });

  it("leaves a half-typed value alone so typing never fights the user", () => {
    expect(sanitisePhoneInput("")).toBe("");
    expect(sanitisePhoneInput("0")).toBe("0");
    expect(sanitisePhoneInput("077")).toBe("077");
  });
});
