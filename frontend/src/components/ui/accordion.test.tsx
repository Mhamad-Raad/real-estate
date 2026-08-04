import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Accordion, AccordionItem } from "./accordion";

// The `locked` prop is the UI half of progressive step unlocking (§5.2) — a locked step must
// never be openable and must never mount its body.
describe("AccordionItem", () => {
  it("opens and closes when it is not locked", async () => {
    render(
      <AccordionItem title="Step 2">
        <p>step body</p>
      </AccordionItem>,
    );
    expect(screen.queryByText("step body")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Step 2/ }));
    expect(screen.getByText("step body")).toBeInTheDocument();
  });

  it("cannot be opened while locked and keeps its body unmounted", async () => {
    render(
      <AccordionItem title="Step 3" locked>
        <p>step body</p>
      </AccordionItem>,
    );
    const header = screen.getByRole("button", { name: /Step 3/ });
    expect(header).toBeDisabled();
    await userEvent.click(header);
    expect(screen.queryByText("step body")).not.toBeInTheDocument();
  });

  it("ignores defaultOpen when locked", () => {
    render(
      <AccordionItem title="Step 4" locked defaultOpen>
        <p>step body</p>
      </AccordionItem>,
    );
    expect(screen.queryByText("step body")).not.toBeInTheDocument();
  });

  it("expands itself once it unlocks and becomes the default step", () => {
    const item = (locked: boolean, defaultOpen: boolean) => (
      <AccordionItem title="Step 3" locked={locked} defaultOpen={defaultOpen}>
        <p>step body</p>
      </AccordionItem>
    );
    // Mounts locked (a step the lawyer hasn't reached), then Proceed unlocks it.
    const { rerender } = render(item(true, false));
    expect(screen.queryByText("step body")).not.toBeInTheDocument();
    rerender(item(false, true));
    expect(screen.getByText("step body")).toBeInTheDocument();
  });

  it("stays closed when it unlocks but is not the default step", () => {
    const item = (locked: boolean) => (
      <AccordionItem title="Step 4" locked={locked} defaultOpen={false}>
        <p>step body</p>
      </AccordionItem>
    );
    const { rerender } = render(item(true));
    rerender(item(false));
    expect(screen.queryByText("step body")).not.toBeInTheDocument();
  });
});

// Single-open mode: working a step must not leave the previous ones expanded (UC-051).
describe("Accordion in single-open mode", () => {
  const Group = ({ openStep = 1, single = true }: { openStep?: number; single?: boolean }) => (
    <Accordion single={single}>
      {[1, 2, 3].map((n) => (
        <AccordionItem key={n} itemKey={String(n)} title={`Step ${n}`} defaultOpen={n === openStep}>
          <p>body {n}</p>
        </AccordionItem>
      ))}
    </Accordion>
  );

  it("opens the default section, so the lawyer lands on the step they are on", () => {
    render(<Group openStep={2} />);
    expect(screen.getByText("body 2")).toBeInTheDocument();
    expect(screen.queryByText("body 1")).not.toBeInTheDocument();
  });

  it("closes the previous section when another is opened", async () => {
    render(<Group />);
    expect(screen.getByText("body 1")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Step 3/ }));

    expect(screen.getByText("body 3")).toBeInTheDocument();
    expect(screen.queryByText("body 1")).not.toBeInTheDocument();
  });

  it("leaves a plain group independent, so several may stand open", async () => {
    render(<Group single={false} />);
    await userEvent.click(screen.getByRole("button", { name: /Step 3/ }));

    expect(screen.getByText("body 1")).toBeInTheDocument();
    expect(screen.getByText("body 3")).toBeInTheDocument();
  });
});
