import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Checkbox } from "./checkbox";

// The check glyph is absolutely positioned against the **wrapper**, so any layout class a caller
// passes has to land there too. Put on the input instead, `mt-0.5` moved the box down while the
// tick stayed — the check sat 2px high in a 16px box, and only on the two checkboxes that pass a
// margin (the scan-review acknowledgement and "has a spouse"), which is why it read as random.
describe("Checkbox", () => {
  it("puts a caller's layout class on the wrapper, not the input", () => {
    render(<Checkbox className="mt-0.5" aria-label="ack" />);

    const input = screen.getByLabelText("ack");
    expect(input.className).not.toMatch(/mt-0\.5/);
    expect(input.parentElement?.className).toMatch(/mt-0\.5/);
  });

  it("keeps its own box styling on the input, where the checked/indeterminate states apply", () => {
    render(<Checkbox className="mt-0.5" aria-label="ack" />);

    // These are `peer` states the glyph selects on; moving them would break the tick entirely.
    expect(screen.getByLabelText("ack").className).toMatch(/peer/);
    expect(screen.getByLabelText("ack").className).toMatch(/checked:bg-primary/);
  });
});

// The three primitives that can hold a rejected field must mark it the same way, or a form author
// has to remember which one supports what.
describe("invalid state parity across the form primitives", () => {
  it("Input, Select and Textarea all expose it", async () => {
    const { Input } = await import("./input");
    const { Select } = await import("./select");
    const { Textarea } = await import("./textarea");

    render(
      <>
        <Input invalid aria-label="i" />
        <Select invalid aria-label="s" />
        <Textarea invalid aria-label="t" />
      </>,
    );

    for (const name of ["i", "s", "t"]) {
      const el = screen.getByLabelText(name);
      expect(el).toHaveAttribute("aria-invalid", "true");
      expect(el.className).toMatch(/border-destructive/);
    }
  });
});
