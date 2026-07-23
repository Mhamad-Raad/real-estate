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
    expect(screen.getByText("Page 1 of 3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Previous/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Next/i })).toBeEnabled();
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
