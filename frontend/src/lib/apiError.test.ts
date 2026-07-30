import { describe, expect, it } from "vitest";

import { apiErrorMessage, apiErrorStatus, apiInUseTotal } from "./apiError";

describe("apiErrorMessage", () => {
  it("prefers DRF's detail", () => {
    expect(apiErrorMessage({ data: { detail: "Nope." } }, "fallback")).toBe("Nope.");
  });

  it("falls back to the first field error", () => {
    expect(apiErrorMessage({ data: { file: ["Bad file."] } }, "fallback")).toBe("Bad file.");
  });

  it("uses the fallback when there is nothing usable", () => {
    expect(apiErrorMessage({ status: 500 }, "fallback")).toBe("fallback");
  });
});

describe("apiErrorStatus", () => {
  it("reads the status when present", () => {
    expect(apiErrorStatus({ status: 409 })).toBe(409);
    expect(apiErrorStatus({})).toBeUndefined();
  });
});

describe("apiInUseTotal", () => {
  it("sums the blocking counts DRF sends as strings", () => {
    // Real shape observed from the API: ValidationError renders every value as a string.
    const err = { status: 400, data: { detail: "…", in_use: { processes: "9", clients: "7" } } };
    expect(apiInUseTotal(err)).toBe(16);
  });

  it("also handles plain numbers", () => {
    expect(apiInUseTotal({ data: { in_use: { processes: 2 } } })).toBe(2);
  });

  it("is undefined for an unrelated error, so the caller shows its own message", () => {
    expect(apiInUseTotal({ data: { detail: "Not found." } })).toBeUndefined();
    expect(apiInUseTotal({ status: 500 })).toBeUndefined();
    expect(apiInUseTotal({ data: { in_use: {} } })).toBeUndefined();
  });
});
