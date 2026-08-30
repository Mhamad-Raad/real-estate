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

  it("refuses a day the month does not have", async () => {
    const onChange = vi.fn();
    render(<Controlled onChange={onChange} />);

    await userEvent.type(boxes().day, "31");
    await userEvent.type(boxes().month, "02");
    await userEvent.type(boxes().year, "2026");

    expect(onChange).not.toHaveBeenCalled();
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
