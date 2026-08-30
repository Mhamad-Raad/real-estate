import { describe, expect, it } from "vitest";

import { PID_MAX_DIGITS, filterPid } from "./pid";

// The box mirrors `common/validators.validate_pid`; if the two drift, the field and the API
// disagree about one value (the same rule the phone box follows).
describe("filterPid", () => {
  it("keeps digits and drops everything else", () => {
    expect(filterPid("199a001-011 234")).toBe("199001011234");
  });

  it("folds Arabic-Indic and Persian digits to ASCII", () => {
    // The office writes numbers in their own script, and the PID is the dedup key — `١٩٩٠` and
    // `1990` would be different strings to the index.
    expect(filterPid("١٩٩٠٠١٠١١٢٣٤")).toBe("199001011234");
    expect(filterPid("۱۹۹۰۰۱۰۱۱۲۳۴")).toBe("199001011234");
  });

  it("caps at twelve, dropping from the end", () => {
    // Truncating the start would rewrite a number under the cursor mid-type.
    expect(filterPid("1990010112349999")).toBe("199001011234");
    expect(filterPid("1990010112349999")).toHaveLength(PID_MAX_DIGITS);
  });

  it("keeps leading and trailing zeros, which are ordinary in an ID", () => {
    expect(filterPid("007123456000")).toBe("007123456000");
  });

  it("lets a partial entry through — it is a filter, not the validator", () => {
    expect(filterPid("1990")).toBe("1990");
    expect(filterPid("")).toBe("");
  });
});
