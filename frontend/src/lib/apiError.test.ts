import { describe, expect, it } from "vitest";

import {
  apiErrorMessage,
  apiErrorStatus,
  apiInUseTotal,
  fieldErrors,
  translateApiMessage,
} from "./apiError";

// The exact payload the intake endpoint returns for a mistyped birth year, captured from the
// running API. It is nested under `client_data`, which is what used to make it invisible.
const NESTED_DOB = {
  status: 400,
  data: {
    client_data: {
      date_of_birth: ["Date has wrong format. Use one of these formats instead: YYYY-MM-DD."],
    },
  },
};

describe("apiErrorMessage", () => {
  it("prefers DRF's detail", () => {
    expect(apiErrorMessage({ data: { detail: "Nope." } }, "fallback")).toBe("Nope.");
  });

  it("falls back to the first field error", () => {
    expect(apiErrorMessage({ data: { file: ["Bad file."] } }, "fallback")).toBe("Bad file.");
  });

  it("reaches an error nested under a nested serializer", () => {
    // The regression: this returned "fallback", so a mistyped date reported nothing at all.
    expect(apiErrorMessage(NESTED_DOB, "fallback")).toMatch(/Date has wrong format/);
  });

  it("names the field when a label is supplied", () => {
    expect(apiErrorMessage(NESTED_DOB, "fallback", (f) => (f === "date_of_birth" ? "Date of birth" : undefined))).toBe(
      "Date of birth: Date has wrong format. Use one of these formats instead: YYYY-MM-DD.",
    );
  });

  it("prefers a non_field_errors sentence over guessing at a field", () => {
    expect(apiErrorMessage({ data: { non_field_errors: ["Pick one."] } }, "fallback")).toBe("Pick one.");
  });

  it("uses the fallback when there is nothing usable", () => {
    expect(apiErrorMessage({ status: 500 }, "fallback")).toBe("fallback");
  });
});

describe("fieldErrors", () => {
  it("flattens a nested serializer's errors to the leaf field name", () => {
    expect(fieldErrors(NESTED_DOB)).toEqual({
      date_of_birth: "Date has wrong format. Use one of these formats instead: YYYY-MM-DD.",
    });
  });

  it("collects several fields at once, so every bad input can be marked", () => {
    const err = { data: { client_data: { phone: ["Bad phone."] }, land_id: ["Required."] } };
    expect(fieldErrors(err)).toEqual({ phone: "Bad phone.", land_id: "Required." });
  });

  it("keeps whole-request errors out — they belong to no input", () => {
    const err = { data: { detail: "Nope.", non_field_errors: ["Pick one."], phone: ["Bad."] } };
    expect(fieldErrors(err)).toEqual({ phone: "Bad." });
  });

  it("is empty for a network or server error, so the caller shows its own message", () => {
    expect(fieldErrors({ status: 500 })).toEqual({});
    expect(fieldErrors(undefined)).toEqual({});
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

describe("translateApiMessage", () => {
  const t = (key: string) => (key === "errors.phone.chars" ? "ژمارەی تەلەفۆن…" : key);

  it("translates a server message that is one of our keys", () => {
    expect(translateApiMessage("errors.phone.chars", t)).toBe("ژمارەی تەلەفۆن…");
  });

  it("leaves DRF's own English sentences alone", () => {
    // These are not keys and have no translation; passing them through beats blanking them.
    expect(translateApiMessage("This field is required.", t)).toBe("This field is required.");
  });

  it("never shows a raw key when the translation is missing", () => {
    // i18next echoes the key back. Showing that would be worse than the English it replaced.
    expect(translateApiMessage("errors.unknown.key", t)).toBe("errors.unknown.key");
  });

  it("flows through fieldErrors, so the inline message is translated too", () => {
    const err = { data: { client_data: { phone: ["errors.phone.chars"] } } };
    expect(fieldErrors(err, t)).toEqual({ phone: "ژمارەی تەلەفۆن…" });
  });

  it("flows through apiErrorMessage alongside the field label", () => {
    const err = { data: { phone: ["errors.phone.chars"] } };
    expect(apiErrorMessage(err, "fallback", () => "تەلەفۆن", t)).toBe("تەلەفۆن: ژمارەی تەلەفۆن…");
  });
});

// Shapes that existed BEFORE the validation work. `apiErrorMessage` was rewritten to see
// through DRF's nesting, and these pin that the rewrite changed nothing for the callers that
// already depended on it — the delete-refusal counts above all, which must never mark a field.
describe("pre-existing error shapes (regression)", () => {
  it("in_use delete refusal still reads its counts and is not treated as a field", () => {
    const err = { status: 400, data: { detail: "In use.", in_use: { processes: "9", clients: "7" } } };
    expect(apiInUseTotal(err)).toBe(16);
    expect(fieldErrors(err)).toEqual({});          // `in_use` must never mark an input
    expect(apiErrorMessage(err, "fb")).toBe("In use.");
  });

  it("a 409 optimistic-lock conflict still yields its detail", () => {
    expect(apiErrorMessage({ status: 409, data: { detail: "Stale version." } }, "fb")).toBe("Stale version.");
  });

  it("a bare-string body is still passed through", () => {
    expect(apiErrorMessage({ status: 500, data: "Server exploded" }, "fb")).toBe("Server exploded");
  });

  it("a network error with no body still falls back", () => {
    expect(apiErrorMessage({ status: "FETCH_ERROR" }, "fb")).toBe("fb");
    expect(fieldErrors({ status: "FETCH_ERROR" })).toEqual({});
  });

  it("the old flat single-field shape still resolves the same message", () => {
    expect(apiErrorMessage({ data: { file: ["Bad file."] } }, "fb")).toBe("Bad file.");
  });
});

describe("a key that carries a name", () => {
  // `errors.pid.taken:<full name>` — the one message with a runtime value in it. The validators
  // are otherwise parameterless because their bounds are constants; a national ID's holder is not.
  const t = (key: string, params?: Record<string, string>) =>
    key === "errors.pid.taken" ? `This national ID already belongs to ${params?.name}.` : key;

  /** The rendered text with the bidi isolates stripped — they are invisible to a reader. */
  const readable = (message: string) => message.replace(/[\u2068\u2069]/g, "");

  it("translates the key and fills the name in", () => {
    expect(readable(translateApiMessage("errors.pid.taken:Karwan Ahmed", t))).toBe(
      "This national ID already belongs to Karwan Ahmed.",
    );
  });

  it("reaches the form field it belongs to", () => {
    const errors = fieldErrors({ data: { pid: ["errors.pid.taken:Karwan Ahmed"] } }, t);

    expect(readable(errors.pid)).toBe("This national ID already belongs to Karwan Ahmed.");
  });

  it("isolates the name so it cannot reorder the sentence around it", () => {
    // §9: a Latin name inside a Sorani sentence needs a bidi isolate, or the words either side of
    // it swap. The office's names come in both scripts.
    const seen = translateApiMessage("errors.pid.taken:Karwan Ahmed", (_k, p) => p?.name ?? "");

    expect(seen.startsWith("\u2068")).toBe(true); // First Strong Isolate
    expect(seen.endsWith("\u2069")).toBe(true); // Pop Directional Isolate
  });

  it("survives a name with spaces, Sorani script or punctuation", () => {
    expect(translateApiMessage("errors.pid.taken:کاروان ئەحمەد", t)).toContain("کاروان ئەحمەد");
    expect(translateApiMessage("errors.pid.taken:O'Brien, A.", t)).toContain("O'Brien, A.");
  });

  it("shows the raw message when the key has no translation", () => {
    // The safety net every other key has: a bare `errors.…` in front of a user is worse than the
    // English sentence it replaced.
    expect(translateApiMessage("errors.pid.unknown:Someone", (k) => k)).toBe(
      "errors.pid.unknown:Someone",
    );
  });

  it("leaves an ordinary English sentence containing a colon alone", () => {
    const sentence = "Date has wrong format. Use one of these formats instead: YYYY-MM-DD.";

    expect(translateApiMessage(sentence, t)).toBe(sentence);
  });

  it("still handles a plain key with no name", () => {
    expect(translateApiMessage("errors.phone.chars", (k) => (k === "errors.phone.chars" ? "Digits only." : k))).toBe(
      "Digits only.",
    );
  });
});
