import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { useAutosave } from "./useAutosave";

// A stand-in for one autosaving panel: `saved` is what the server holds, and the harness only
// applies a patch when told to, so a slow round trip can be simulated.
function Panel({
  onSave,
  saved,
}: {
  onSave: (patch: Partial<{ start_date: string | null }>) => void;
  saved: { start_date: string | null };
}) {
  const field = useAutosave({ saved, onSave, delay: 50 });
  return (
    <input
      aria-label="start"
      type="text"
      value={field.value("start_date") ?? ""}
      onChange={(e) => field.set("start_date", e.target.value)}
      onBlur={field.flush}
    />
  );
}

describe("useAutosave", () => {
  it("sends one request for a burst of edits, carrying the settled value", async () => {
    const onSave = vi.fn();
    render(<Panel onSave={onSave} saved={{ start_date: null }} />);

    await userEvent.type(screen.getByLabelText("start"), "2026");

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    expect(onSave).toHaveBeenCalledWith({ start_date: "2026" });
  });

  it("keeps showing what was typed while the server still holds the old value", async () => {
    // The reset bug: a date input reports a valid date per year keystroke, so the refetch used to
    // write the server's half-typed value back into the control mid-edit.
    const { rerender } = render(<Panel onSave={vi.fn()} saved={{ start_date: "0002-08-16" }} />);
    const input = screen.getByLabelText<HTMLInputElement>("start");

    await userEvent.clear(input);
    await userEvent.type(input, "2026-08-16");
    rerender(<Panel onSave={vi.fn()} saved={{ start_date: "0002-08-16" }} />);

    expect(input.value).toBe("2026-08-16");
  });

  it("hands control back to the server once it echoes the value", async () => {
    const onSave = vi.fn();
    function Harness() {
      const [saved, setSaved] = useState<{ start_date: string | null }>({ start_date: null });
      return (
        <>
          <Panel onSave={onSave} saved={saved} />
          <button onClick={() => setSaved({ start_date: "2026-08-16" })}>server</button>
        </>
      );
    }
    render(<Harness />);
    const input = screen.getByLabelText<HTMLInputElement>("start");

    await userEvent.type(input, "2026-08-16");
    await userEvent.click(screen.getByText("server"));
    // The draft is retired, so a later correction from the other computer now shows through.
    expect(input.value).toBe("2026-08-16");
  });

  it("saves a pending edit when the panel unmounts", async () => {
    const onSave = vi.fn();
    const { rerender } = render(<Panel onSave={onSave} saved={{ start_date: null }} />);

    await userEvent.type(screen.getByLabelText("start"), "20");
    // Collapsing the step unmounts the panel before the timer would have fired.
    rerender(<div />);

    expect(onSave).toHaveBeenCalledWith({ start_date: "20" });
  });
});
