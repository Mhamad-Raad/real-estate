import { describe, expect, it } from "vitest";

import {
  daysInMonth,
  isRealDate,
  monthGrid,
  parsePasted,
  segmentInput,
  segmentIsFinished,
  settledSegment,
  stepSegment,
  shiftMonth,
  toIso,
  toParts,
} from "./date";

describe("toIso", () => {
  it("builds a date once the three boxes name a real day", () => {
    expect(toIso({ day: "05", month: "08", year: "2026" })).toBe("2026-08-05");
    expect(toIso({ day: "5", month: "8", year: "2026" })).toBe("2026-08-05");
  });

  it("holds a year that is still being typed", () => {
    // The whole reason this returns null: a native date input called every one of these valid,
    // which is how the year 2 was saved (UC-072).
    for (const year of ["2", "20", "202"]) {
      expect(toIso({ day: "05", month: "08", year })).toBeNull();
    }
    expect(toIso({ day: "05", month: "08", year: "2026" })).toBe("2026-08-05");
  });

  it("refuses a day the month does not have rather than rolling it forward", () => {
    // `new Date(2026, 1, 31)` is 3 March. A date field that silently did that would store a day
    // nobody typed.
    expect(toIso({ day: "31", month: "02", year: "2026" })).toBeNull();
    expect(toIso({ day: "29", month: "02", year: "2024" })).toBe("2024-02-29");
    expect(toIso({ day: "29", month: "02", year: "2026" })).toBeNull();
  });

  it("holds an incomplete date", () => {
    expect(toIso({ day: "", month: "08", year: "2026" })).toBeNull();
    expect(toIso({ day: "05", month: "", year: "2026" })).toBeNull();
  });
});

describe("toParts", () => {
  it("splits an ISO date into the three boxes", () => {
    expect(toParts("2026-08-05")).toEqual({ day: "05", month: "08", year: "2026" });
  });

  it("comes back empty rather than half-filled for anything else", () => {
    for (const value of ["", null, undefined, "2026-08", "not a date"]) {
      expect(toParts(value)).toEqual({ day: "", month: "", year: "" });
    }
  });
});

describe("segmentInput", () => {
  it("keeps digits in any script, folded to ASCII", () => {
    expect(segmentInput("٢٦", 2)).toBe("26");
    expect(segmentInput("۲۰۲۶", 4)).toBe("2026");
  });

  it("drops everything that is not a digit and caps the length", () => {
    expect(segmentInput("a1b2c3", 2)).toBe("12");
  });
});

describe("segmentIsFinished", () => {
  it("moves on when the box is full", () => {
    expect(segmentIsFinished("day", "05")).toBe(true);
    expect(segmentIsFinished("year", "2026")).toBe(true);
    expect(segmentIsFinished("year", "202")).toBe(false);
  });

  it("moves on early when one digit cannot grow into anything valid", () => {
    // A 5 in the month box is May and can be nothing else; a 1 could still become 12.
    expect(segmentIsFinished("month", "5")).toBe(true);
    expect(segmentIsFinished("month", "1")).toBe(false);
    expect(segmentIsFinished("day", "4")).toBe(true);
    expect(segmentIsFinished("day", "3")).toBe(false);
  });
});

describe("parsePasted", () => {
  it("takes an ISO date, which is what a copy out of this app gives", () => {
    expect(parsePasted("2026-08-05")).toEqual({ day: "05", month: "08", year: "2026" });
  });

  it("takes a day-first date, which is what the office reads off the paperwork", () => {
    expect(parsePasted("5/8/2026")).toEqual({ day: "05", month: "08", year: "2026" });
    expect(parsePasted(" 05.08.2026 ")).toEqual({ day: "05", month: "08", year: "2026" });
  });

  it("takes one written in Arabic-Indic digits", () => {
    expect(parsePasted("٢٠٢٦-٠٨-٠٥")).toEqual({ day: "05", month: "08", year: "2026" });
  });

  it("refuses a bare run of digits rather than guessing the order", () => {
    // `05082026` and `20260805` look alike, and guessing wrong writes a date nobody typed.
    expect(parsePasted("05082026")).toBeNull();
  });

  it("refuses anything that is not a real day", () => {
    expect(parsePasted("31/02/2026")).toBeNull();
    expect(parsePasted("hello")).toBeNull();
  });
});

describe("settledSegment", () => {
  it("gives a lone day or month digit its zero", () => {
    expect(settledSegment("day", "5")).toBe("05");
    expect(settledSegment("month", "9")).toBe("09");
  });

  it("leaves a full box, and the year, as they are", () => {
    expect(settledSegment("day", "15")).toBe("15");
    expect(settledSegment("year", "202")).toBe("202"); // half-typed, not 0202
  });

  it("leaves a lone zero alone — it is not a day", () => {
    expect(settledSegment("day", "0")).toBe("0");
  });
});

describe("stepSegment", () => {
  const parts = { day: "05", month: "08", year: "2026" };

  it("steps a box up and down", () => {
    expect(stepSegment("day", parts, 1)).toBe("06");
    expect(stepSegment("month", parts, -1)).toBe("07");
    expect(stepSegment("year", parts, 1)).toBe("2027");
  });

  it("wraps the day and the month rather than stopping dead", () => {
    expect(stepSegment("month", { ...parts, month: "12" }, 1)).toBe("01");
    expect(stepSegment("month", { ...parts, month: "01" }, -1)).toBe("12");
    expect(stepSegment("day", { ...parts, day: "01" }, -1)).toBe("31");
  });

  it("stops the day at the length of the month it is in", () => {
    expect(stepSegment("day", { day: "28", month: "02", year: "2026" }, 1)).toBe("01");
    expect(stepSegment("day", { day: "28", month: "02", year: "2024" }, 1)).toBe("29");
  });

  it("clamps the year instead of wrapping — 1900 up from 2200 is not what anyone meant", () => {
    expect(stepSegment("year", { ...parts, year: "2200" }, 1)).toBe("2200");
    expect(stepSegment("year", { ...parts, year: "1900" }, -1)).toBe("1900");
  });

  it("starts an empty box somewhere useful", () => {
    const empty = { day: "", month: "", year: "" };

    expect(stepSegment("month", empty, 1)).toBe("01");
    expect(stepSegment("month", empty, -1)).toBe("12");
    expect(stepSegment("year", empty, 1)).toBe(String(new Date().getFullYear()));
  });
});

describe("the calendar arithmetic", () => {
  it("knows how long a month is, leap years included", () => {
    expect(daysInMonth(2026, 2)).toBe(28);
    expect(daysInMonth(2024, 2)).toBe(29);
    expect(daysInMonth(2026, 8)).toBe(31);
  });

  it("pads every week to seven cells and holds every day exactly once", () => {
    const grid = monthGrid(2026, 8, 6);

    expect(grid.every((week) => week.length === 7)).toBe(true);
    expect(grid.flat().filter((d) => d !== null)).toEqual(
      Array.from({ length: 31 }, (_, i) => i + 1),
    );
  });

  it("starts the month under the weekday the office's week starts on", () => {
    // 1 August 2026 is a Saturday, so a Saturday-first week has no lead padding and a
    // Sunday-first one has six.
    expect(monthGrid(2026, 8, 6)[0][0]).toBe(1);
    expect(monthGrid(2026, 8, 0)[0].slice(0, 6)).toEqual([null, null, null, null, null, null]);
  });

  it("carries the year when stepping past a boundary", () => {
    expect(shiftMonth(2026, 1, -1)).toEqual({ year: 2025, month: 12 });
    expect(shiftMonth(2026, 12, 1)).toEqual({ year: 2027, month: 1 });
    expect(shiftMonth(2026, 8, -20)).toEqual({ year: 2024, month: 12 });
  });

  it("refuses a year outside the window a typed date can land in", () => {
    expect(isRealDate(1899, 8, 5)).toBe(false);
    expect(isRealDate(1900, 8, 5)).toBe(true);
  });
});
