import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import i18n from "i18next";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Calendar } from "./calendar";

afterEach(async () => {
  await i18n.changeLanguage("en");
});

const day = (name: string) => screen.getByRole("button", { name });

describe("Calendar", () => {
  it("marks the chosen day", () => {
    render(<Calendar value="2026-08-05" onPick={() => {}} />);

    expect(day("5")).toHaveAttribute("aria-selected", "true");
    expect(day("6")).toHaveAttribute("aria-selected", "false");
  });

  it("is one tab stop, not thirty", () => {
    render(<Calendar value="2026-08-05" onPick={() => {}} />);

    expect(day("5")).toHaveAttribute("tabindex", "0");
    expect(day("6")).toHaveAttribute("tabindex", "-1");
  });

  it("walks the grid with the arrow keys", async () => {
    render(<Calendar value="2026-08-05" onPick={() => {}} />);
    day("5").focus();

    await userEvent.keyboard("{ArrowDown}");

    expect(day("12")).toHaveFocus();
  });

  it("turns the page when an arrow crosses the edge of the month", async () => {
    // A birth date decades back is unreachable if the arrows stop at the 1st.
    render(<Calendar value="2026-08-01" onPick={() => {}} />);
    day("1").focus();

    await userEvent.keyboard("{ArrowLeft}");

    expect(screen.getByText(/July 2026/)).toBeInTheDocument();
    expect(day("31")).toHaveFocus();
  });

  it("reports the day it was given, not the day it was showing", async () => {
    const onPick = vi.fn();
    render(<Calendar value="2026-08-05" onPick={onPick} />);

    await userEvent.click(day("17"));

    expect(onPick).toHaveBeenCalledWith("2026-08-17");
  });

  it("does not steal the caret out of the boxes when it opens", () => {
    render(<Calendar value="2026-08-05" onPick={() => {}} />);

    expect(day("5")).not.toHaveFocus();
  });

  it("names the month and the weekdays in the interface language", async () => {
    await i18n.changeLanguage("ckb");

    render(<Calendar value="2026-08-05" onPick={() => {}} />);

    // Sorani has no Intl date data of its own, so both RTL languages read Arabic's month names —
    // the same rule `lib/format.ts` follows for every displayed date.
    expect(screen.getByText(/٢٠٢٦/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "٥" })).toBeInTheDocument();
  });

  it("starts the Kurdish week on Saturday and the English week on Sunday", async () => {
    // 1 August 2026 is a Saturday, so a Saturday-first month opens flush against the edge while a
    // Sunday-first one carries six blank cells before it.
    const lead = () =>
      [...screen.getByRole("grid").children].findIndex((cell) => cell.tagName === "BUTTON");
    const { unmount } = render(<Calendar value="2026-08-01" onPick={() => {}} />);
    const english = lead();
    unmount();

    await i18n.changeLanguage("ckb");
    render(<Calendar value="2026-08-01" onPick={() => {}} />);

    expect(english).toBe(6);
    expect(lead()).toBe(0);
  });
});
