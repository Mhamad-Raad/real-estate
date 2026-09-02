import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { DateField } from "./date-field";

const boxes = () => ({
  day: screen.getByLabelText("Day"),
  month: screen.getByLabelText("Month"),
  year: screen.getByLabelText("Year"),
});

/** The real thing a call site does: hold the value and feed it back. */
function Controlled({ initial = "", onChange }: { initial?: string; onChange?: (v: string) => void }) {
  const [value, setValue] = useState(initial);
  return (
    <DateField
      value={value}
      onChange={(next) => {
        setValue(next);
        onChange?.(next);
      }}
    />
  );
}

describe("DateField", () => {
  it("shows a stored date as day, month and year", () => {
    render(<DateField value="2026-08-05" onChange={() => {}} />);

    expect(boxes().day).toHaveValue("05");
    expect(boxes().month).toHaveValue("08");
    expect(boxes().year).toHaveValue("2026");
  });

  it("reads day before month, whatever the language", () => {
    // The whole point of UC-108: a native input took this order from a browser setting, so the
    // office saw month/day/year and nothing in the app could say otherwise.
    render(<DateField value="2026-08-05" onChange={() => {}} />);

    const typed = screen.getAllByRole("textbox").map((box) => (box as HTMLInputElement).value);

    expect(typed).toEqual(["05", "08", "2026"]);
  });

  it("reports nothing until the three boxes name a real day", async () => {
    const onChange = vi.fn();
    render(<Controlled onChange={onChange} />);

    await userEvent.type(boxes().day, "05");
    await userEvent.type(boxes().month, "08");
    expect(onChange).not.toHaveBeenCalled();

    await userEvent.type(boxes().year, "2026");

    expect(onChange).toHaveBeenCalledExactlyOnceWith("2026-08-05");
  });

  it("never reports the years a half-typed 2026 passes through", async () => {
    // UC-072: 2, 20 and 202 are each a valid `<input type="date">` value, and the year 2 reached
    // the database because of it.
    const onChange = vi.fn();
    render(<Controlled initial="" onChange={onChange} />);
    await userEvent.type(boxes().day, "05");
    await userEvent.type(boxes().month, "08");

    await userEvent.type(boxes().year, "2026");

    expect(onChange.mock.calls.flat()).toEqual(["2026-08-05"]);
  });

  it("accepts Arabic-Indic digits, which is how the office types", async () => {
    const onChange = vi.fn();
    render(<Controlled onChange={onChange} />);

    await userEvent.type(boxes().day, "٠٥");
    await userEvent.type(boxes().month, "٠٨");
    await userEvent.type(boxes().year, "٢٠٢٦");

    expect(onChange).toHaveBeenCalledWith("2026-08-05");
  });

  it("writes a lone day or month digit with its zero", async () => {
    const onChange = vi.fn();
    render(<Controlled onChange={onChange} />);

    await userEvent.type(boxes().day, "5");

    expect(boxes().day).toHaveValue("05");
  });

  it("waits for the cursor to leave before adding the zero", async () => {
    // Padding a 1 in the month box the moment it is typed would put 12 out of reach.
    render(<Controlled />);

    await userEvent.type(boxes().month, "1");
    expect(boxes().month).toHaveValue("1");

    // Typed on, not clicked into again — clicking selects the box, which is what makes typing
    // over a stored value work.
    await userEvent.keyboard("2");
    expect(boxes().month).toHaveValue("12");
  });

  it("adds the zero when the box is left by hand", async () => {
    render(<Controlled />);

    await userEvent.type(boxes().month, "1");
    await userEvent.tab();

    expect(boxes().month).toHaveValue("01");
  });

  it("leaves the year alone — 202 is half-typed, not 0202", async () => {
    render(<Controlled />);

    await userEvent.type(boxes().year, "202");
    await userEvent.tab();

    expect(boxes().year).not.toHaveValue("0202");
  });

  it("moves to the next box on its own", async () => {
    render(<Controlled />);

    await userEvent.type(boxes().day, "05");

    expect(boxes().month).toHaveFocus();
  });

  it("moves on early when a digit cannot grow into anything valid", async () => {
    render(<Controlled />);

    await userEvent.type(boxes().day, "5");

    expect(boxes().month).toHaveFocus();
  });

  it("steps back when backspace is pressed in an empty box", async () => {
    render(<Controlled />);
    boxes().month.focus();

    await userEvent.keyboard("{Backspace}");

    expect(boxes().day).toHaveFocus();
  });

  it("selects the whole box when it is clicked, so typing replaces it", async () => {
    render(<Controlled initial="2026-08-05" />);
    const year = boxes().year as HTMLInputElement;

    await userEvent.click(year);

    expect(year.selectionStart).toBe(0);
    expect(year.selectionEnd).toBe(4);
  });

  it("selects the box reached by tabbing into it", async () => {
    render(<Controlled initial="2026-08-05" />);
    boxes().day.focus();

    await userEvent.tab();

    const month = boxes().month as HTMLInputElement;
    expect(month).toHaveFocus();
    expect([month.selectionStart, month.selectionEnd]).toEqual([0, 2]);
  });

  it("walks the boxes with left and right", async () => {
    render(<Controlled initial="2026-08-05" />);
    boxes().day.focus();

    await userEvent.keyboard("{ArrowRight}");
    expect(boxes().month).toHaveFocus();

    await userEvent.keyboard("{ArrowRight}");
    expect(boxes().year).toHaveFocus();

    await userEvent.keyboard("{ArrowLeft}");
    expect(boxes().month).toHaveFocus();
  });

  it("stays put when an arrow would leave the date", async () => {
    render(<Controlled initial="2026-08-05" />);
    boxes().day.focus();

    await userEvent.keyboard("{ArrowLeft}");

    expect(boxes().day).toHaveFocus();
  });

  it("comes back with shift+tab", async () => {
    render(<Controlled initial="2026-08-05" />);
    boxes().year.focus();

    await userEvent.tab({ shift: true });

    expect(boxes().month).toHaveFocus();
  });

  it("steps a box up and down with the arrows", async () => {
    const onChange = vi.fn();
    render(<Controlled initial="2026-08-05" onChange={onChange} />);
    boxes().month.focus();

    await userEvent.keyboard("{ArrowUp}");
    expect(boxes().month).toHaveValue("09");
    expect(onChange).toHaveBeenLastCalledWith("2026-09-05");

    await userEvent.keyboard("{ArrowDown}{ArrowDown}");
    expect(boxes().month).toHaveValue("07");
  });

  it("wraps the month rather than stopping at December", async () => {
    render(<Controlled initial="2026-12-05" />);
    boxes().month.focus();

    await userEvent.keyboard("{ArrowUp}");

    expect(boxes().month).toHaveValue("01");
  });

  it("refuses a day no month has, at the keystroke", async () => {
    render(<Controlled />);

    await userEvent.type(boxes().day, "39");

    // The 9 was refused: 39 is a day no month has, so the 3 stands alone waiting for its digit.
    expect(boxes().day).toHaveValue("3");
  });

  it("refuses a month past 12 the same way", async () => {
    render(<Controlled />);

    await userEvent.type(boxes().month, "19");

    expect(boxes().month).toHaveValue("1");
  });

  it("caps the day at the month's real length once the month is known", async () => {
    // 30 could never be a February day, so the 3 settles as 03 at once instead of waiting.
    render(<Controlled initial="2026-02-10" />);

    await userEvent.clear(boxes().day);
    await userEvent.type(boxes().day, "3");

    expect(boxes().day).toHaveValue("03");
  });

  it("still takes the 29th of a leap-year February", async () => {
    const onChange = vi.fn();
    render(<Controlled initial="2024-02-10" onChange={onChange} />);

    await userEvent.clear(boxes().day);
    await userEvent.type(boxes().day, "29");

    // Last, not only: with month and year already set, the 2 on its own was already the 2nd.
    expect(onChange).toHaveBeenLastCalledWith("2024-02-29");
  });

  it("pulls the day back when the month typed after it turns out shorter", async () => {
    const onChange = vi.fn();
    render(<Controlled onChange={onChange} />);

    await userEvent.type(boxes().day, "31");
    await userEvent.type(boxes().month, "02");
    // Year still open, so February keeps its leap-year 29 — the honest max so far.
    expect(boxes().day).toHaveValue("29");

    await userEvent.type(boxes().year, "2026");

    // The year settles it: 2026 is no leap year, and the date reported is the one on screen.
    expect(boxes().day).toHaveValue("28");
    expect(onChange).toHaveBeenCalledExactlyOnceWith("2026-02-28");
  });

  it("puts back the stored date when a half-typed one is abandoned", async () => {
    // A field left showing 05/08/20 would claim to hold a date that was never saved.
    render(<Controlled initial="2026-08-05" />);
    await userEvent.clear(boxes().year);
    await userEvent.type(boxes().year, "20");

    await userEvent.tab();
    await userEvent.tab();

    expect(boxes().year).toHaveValue("2026");
  });

  it("fills all three boxes from a pasted date", async () => {
    const onChange = vi.fn();
    render(<Controlled onChange={onChange} />);

    await userEvent.click(boxes().day);
    await userEvent.paste("05/08/2026");

    expect(onChange).toHaveBeenCalledWith("2026-08-05");
    expect(boxes().year).toHaveValue("2026");
  });

  it("clears to empty, which is a real edit", async () => {
    const onChange = vi.fn();
    render(<Controlled initial="2026-08-05" onChange={onChange} />);

    await userEvent.click(screen.getByLabelText("Clear the date"));

    expect(onChange).toHaveBeenCalledWith("");
    expect(boxes().day).toHaveValue("");
  });

  it("offers no clear button when there is nothing to clear", () => {
    render(<Controlled />);

    expect(screen.queryByLabelText("Clear the date")).not.toBeInTheDocument();
  });

  it("takes its name from the label that points at it", () => {
    render(
      <>
        <label htmlFor="dob">Date of birth</label>
        <DateField id="dob" value="" onChange={() => {}} invalid />
      </>,
    );

    expect(screen.getByLabelText("Date of birth")).toHaveAttribute("aria-invalid", "true");
  });

  it("keeps stepping, one press after another", async () => {
    // The handler reads the live copy rather than the render's snapshot, because a **held-down**
    // arrow repeats faster than React re-renders and every repeat would otherwise start from the
    // same value. That batching cannot be reproduced here — `userEvent` re-renders between
    // presses — so this pins the ordinary case and the comment carries the rest.
    render(<Controlled initial="2026-08-05" />);
    boxes().day.focus();

    await userEvent.keyboard("{ArrowUp>3/}");

    expect(boxes().day).toHaveValue("08");
  });

  it("describes the error on the boxes, not on a div nobody can focus", () => {
    render(
      <>
        <label htmlFor="dob">Date of birth</label>
        <DateField id="dob" value="" onChange={() => {}} aria-describedby="dob-error" invalid />
        <p id="dob-error">Enter a real date.</p>
      </>,
    );

    expect(screen.getByLabelText("Date of birth")).toHaveAccessibleDescription("Enter a real date.");
  });

  it("takes nothing while disabled", async () => {
    const onChange = vi.fn();
    render(<DateField value="" onChange={onChange} disabled />);

    await userEvent.type(boxes().day, "05");

    expect(onChange).not.toHaveBeenCalled();
  });
});

describe("DateField calendar", () => {
  const open = () => userEvent.click(screen.getByLabelText("Open the calendar"));

  it("picks a day from the calendar", async () => {
    const onChange = vi.fn();
    render(<Controlled initial="2026-08-05" onChange={onChange} />);
    await open();

    await userEvent.click(screen.getByRole("button", { name: "17" }));

    expect(onChange).toHaveBeenCalledWith("2026-08-17");
    expect(boxes().day).toHaveValue("17");
  });

  it("closes on Escape without choosing", async () => {
    const onChange = vi.fn();
    render(<Controlled initial="2026-08-05" onChange={onChange} />);
    await open();

    await userEvent.keyboard("{Escape}");

    expect(screen.queryByRole("button", { name: "17" })).not.toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
  });

  it("opens on the month being edited", async () => {
    render(<Controlled initial="1994-03-21" />);

    await open();

    expect(screen.getByText(/March 1994/)).toBeInTheDocument();
  });

  it("turns the page a month at a time", async () => {
    render(<Controlled initial="2026-01-05" />);
    await open();

    await userEvent.click(screen.getByLabelText("Previous month"));

    expect(screen.getByText(/December 2025/)).toBeInTheDocument();
  });
});
