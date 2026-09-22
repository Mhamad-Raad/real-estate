import { describe, expect, it } from "vitest";

import { filterName } from "./name";

// A number in a name is printed on the generated letter and caught by nobody, so the box refuses
// one as it is typed (the office, 2026-09-22).
describe("filterName", () => {
  it("drops digits and keeps the rest of the name", () => {
    expect(filterName("Karwan2 Ahmed")).toBe("Karwan Ahmed");
  });

  it("drops Arabic-Indic and Persian digits too", () => {
    // The office types numbers in their own script — an ASCII-only rule would let these in.
    expect(filterName("کاروان٧ ئەحمەد۹")).toBe("کاروان ئەحمەد");
  });

  it("leaves what a name may legitimately carry", () => {
    expect(filterName("Abd al-Rahman O'Neill Jr.")).toBe("Abd al-Rahman O'Neill Jr.");
  });

  it("keeps the spacing exactly as typed, mid-entry", () => {
    // Applied on every keystroke, so it must never trim or reflow a half-typed name.
    expect(filterName("  Karwan ")).toBe("  Karwan ");
    expect(filterName("")).toBe("");
  });
});
