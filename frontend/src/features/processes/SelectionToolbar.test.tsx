import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SelectionToolbar } from "./SelectionToolbar";

const unwrap = vi.fn().mockResolvedValue({ id: 5 });
const generate = vi.fn(() => ({ unwrap }));
const generateCodes = vi.fn(() => ({ unwrap }));

vi.mock("@/app/hooks", () => ({ useAppSelector: () => "token" }));
vi.mock("@/lib/toast", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));
vi.mock("@/features/documents/download", () => ({
  downloadGenerationJob: vi.fn(),
  downloadDocument: vi.fn(),
}));
vi.mock("@/features/documents/generationApi", async () => {
  const actual = await vi.importActual<typeof import("@/features/documents/generationApi")>(
    "@/features/documents/generationApi",
  );
  return {
    ...actual,
    useGenerateProcessListMutation: () => [generate, { isLoading: false }],
    useGenerateProcessCodesMutation: () => [generateCodes, { isLoading: false }],
    useGetGenerationJobQuery: () => ({ data: undefined }),
  };
});

describe("SelectionToolbar", () => {
  it("stays out of the way when nothing is selected", () => {
    const { container } = render(<SelectionToolbar selected={[]} onClear={vi.fn()} stepById={{}} />);

    expect(container).toBeEmptyDOMElement();
  });

  it("shows how many rows the letter will cover", () => {
    render(<SelectionToolbar selected={[1, 2, 3]} onClear={vi.fn()} stepById={{ 1: 3, 2: 3, 3: 3 }} />);

    // The tally is locale-formatted (UC-034), so it carries bidi isolates around the digit.
    expect(screen.getByText(/3.?\s*selected/)).toBeInTheDocument();
  });

  it("sends exactly the selected ids to the server", async () => {
    render(<SelectionToolbar selected={[4, 9]} onClear={vi.fn()} stepById={{ 4: 3, 9: 3 }} />);

    await userEvent.click(screen.getByRole("button", { name: /print list letter/i }));

    expect(generate).toHaveBeenCalledWith({ process_ids: [4, 9] });
  });

  // UC-016: the office reads the button to know which letter it is about to get.
  it("offers the single letter for one row and the list letter for several", () => {
    const { rerender } = render(
      <SelectionToolbar selected={[4]} onClear={vi.fn()} stepById={{ 4: 3 }} />,
    );
    expect(screen.getByRole("button", { name: /print letter/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /print list letter/i })).not.toBeInTheDocument();

    rerender(<SelectionToolbar selected={[4, 9]} onClear={vi.fn()} stepById={{ 4: 3, 9: 3 }} />);
    expect(screen.getByRole("button", { name: /print list letter/i })).toBeInTheDocument();
  });

  // UC-057: the code list only covers cases that have reached the institutes. The server
  // re-checks it, so this button is a courtesy — but it must not invite a request that will 400.
  it("offers the code list once every selected case has reached step 3", async () => {
    render(<SelectionToolbar selected={[4, 9]} onClear={vi.fn()} stepById={{ 4: 3, 9: 5 }} />);

    await userEvent.click(screen.getByRole("button", { name: /print code list/i }));

    expect(generateCodes).toHaveBeenCalledWith({ process_ids: [4, 9] });
  });

  it("will not offer the code list while any selected case is still earlier than step 3", () => {
    render(<SelectionToolbar selected={[4, 9]} onClear={vi.fn()} stepById={{ 4: 3, 9: 2 }} />);

    expect(screen.getByRole("button", { name: /print code list/i })).toBeDisabled();
  });
});
