import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SelectionToolbar } from "./SelectionToolbar";

const unwrap = vi.fn().mockResolvedValue({ id: 5 });
const generate = vi.fn(() => ({ unwrap }));

vi.mock("@/app/hooks", () => ({ useAppSelector: () => "token" }));
vi.mock("@/components/ui/toaster", () => ({
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
    useGetGenerationJobQuery: () => ({ data: undefined }),
  };
});

describe("SelectionToolbar", () => {
  it("stays out of the way when nothing is selected", () => {
    const { container } = render(<SelectionToolbar selected={[]} onClear={vi.fn()} />);

    expect(container).toBeEmptyDOMElement();
  });

  it("shows how many rows the letter will cover", () => {
    render(<SelectionToolbar selected={[1, 2, 3]} onClear={vi.fn()} />);

    expect(screen.getByText("3 selected")).toBeInTheDocument();
  });

  it("sends exactly the selected ids to the server", async () => {
    render(<SelectionToolbar selected={[4, 9]} onClear={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: /print list letter/i }));

    expect(generate).toHaveBeenCalledWith({ process_ids: [4, 9] });
  });

  // UC-016: the office reads the button to know which letter it is about to get.
  it("offers the single letter for one row and the list letter for several", () => {
    const { rerender } = render(<SelectionToolbar selected={[4]} onClear={vi.fn()} />);
    expect(screen.getByRole("button", { name: /print letter/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /print list letter/i })).not.toBeInTheDocument();

    rerender(<SelectionToolbar selected={[4, 9]} onClear={vi.fn()} />);
    expect(screen.getByRole("button", { name: /print list letter/i })).toBeInTheDocument();
  });
});
