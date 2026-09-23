import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { filterKeepingCaret } from "./caret";
import { filterName } from "./name";
import { filterPid } from "./pid";

// A real parent: the caret only misbehaves when React re-renders (or restores) the value itself,
// which a mock `onChange` never triggers.
function Harness({ filter }: { filter: (raw: string) => string }) {
  const [value, setValue] = useState("");
  return (
    <input aria-label="box" value={value} onChange={(e) => setValue(filterKeepingCaret(e.target, filter))} />
  );
}

const box = (filter: (raw: string) => string) => {
  render(<Harness filter={filter} />);
  return screen.getByLabelText("box") as HTMLInputElement;
};

const at = (start: number) => ({ initialSelectionStart: start, initialSelectionEnd: start });

describe("filterKeepingCaret", () => {
  it("holds the caret where the typist was when a character is refused", async () => {
    const el = box(filterName);
    await userEvent.type(el, "Karwan Ahmed");

    await userEvent.type(el, "5", at(6));

    expect(el).toHaveValue("Karwan Ahmed");
    expect(el.selectionStart).toBe(6);
  });

  it("counts the surviving characters rather than subtracting the dropped ones", async () => {
    // A filter that also trims the END — the ID box's 12-digit cap. Length arithmetic put the
    // caret *before* the digit just typed, so the next two came out transposed.
    const el = box(filterPid);
    await userEvent.type(el, "197712120099");

    await userEvent.type(el, "4", at(6));

    expect(el).toHaveValue("197712412009");
    expect(el.selectionStart).toBe(7);
  });

  it("does not touch the selection at all when nothing was refused", async () => {
    // Every ordinary keystroke lands here, and the browser's own caret is already right — a
    // needless `setSelectionRange` is interference (an active IME composition above all).
    const el = box(filterName);
    const spy = vi.spyOn(el, "setSelectionRange");

    await userEvent.type(el, "Karwan");

    expect(el).toHaveValue("Karwan");
    expect(spy).not.toHaveBeenCalled();
  });
});
