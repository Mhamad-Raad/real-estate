import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Pagination } from "./Pagination";

describe("Pagination", () => {
  it("renders nothing when everything fits on one page", () => {
    const { container } = render(<Pagination page={1} count={10} onPage={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the page count and disables Previous on the first page", () => {
    render(<Pagination page={1} count={60} onPage={() => {}} />); // 60 / 25 => 3 pages
    // Both numbers go through the locale formatter (UC-034), which wraps each in bidi isolates —
    // so match on the text content rather than the raw string.
    expect(screen.getByText(/Page\s*.?1.?\s*of\s*.?3.?/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Previous/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Next/i })).toBeEnabled();
  });

  it("renders the page numbers in the active language's digits", () => {
    render(<Pagination page={1} count={60} onPage={() => {}} />);
    // The regression this pins: raw `{{page}}` interpolation printed Latin digits beside Sorani
    // text on all five paginated tables.
    expect(screen.getByText(/Page/).textContent).toMatch(/[⁦-⁩]/);
  });

  it("advances the page when Next is clicked", async () => {
    const onPage = vi.fn();
    render(<Pagination page={1} count={60} onPage={onPage} />);
    await userEvent.click(screen.getByRole("button", { name: /Next/i }));
    expect(onPage).toHaveBeenCalledWith(2);
  });

  it("disables Next on the last page", () => {
    render(<Pagination page={3} count={60} onPage={() => {}} />);
    expect(screen.getByRole("button", { name: /Next/i })).toBeDisabled();
  });
});
