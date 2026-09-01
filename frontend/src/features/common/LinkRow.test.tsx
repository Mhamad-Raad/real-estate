import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { LinkRow } from "./LinkRow";

// The whole row is the way into the detail (UC-119) — but nothing inside it loses its own click.
function renderRow(children: ReactNode) {
  return render(
    <MemoryRouter initialEntries={["/list"]}>
      <Routes>
        <Route
          path="/list"
          element={
            <table>
              <tbody>
                <LinkRow to="/detail/7">
                  {children}
                </LinkRow>
              </tbody>
            </table>
          }
        />
        <Route path="/detail/7" element={<p>detail page</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("LinkRow", () => {
  it("opens the detail when a cell is clicked", () => {
    renderRow(<td>Ahmad</td>);

    fireEvent.click(screen.getByText("Ahmad"));

    expect(screen.getByText("detail page")).toBeInTheDocument();
  });

  it("opens the detail on Enter when the row is focused, and is still a row", () => {
    renderRow(<td>Ahmad</td>);
    // Still a table row for assistive tech — a `<tr>` re-cast as a link loses its cells.
    const row = screen.getByRole("row", { name: /Ahmad/ });

    fireEvent.keyDown(row, { key: "Enter" });

    expect(screen.getByText("detail page")).toBeInTheDocument();
  });

  it("leaves a button inside the row to its own job", () => {
    const onDelete = vi.fn();
    renderRow(
      <td>
        <button type="button" onClick={onDelete}>
          Delete
        </button>
      </td>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    expect(onDelete).toHaveBeenCalledOnce();
    expect(screen.queryByText("detail page")).not.toBeInTheDocument();
  });

  it("does not treat a text selection as a click", () => {
    renderRow(<td>Ahmad</td>);
    const getSelection = vi.spyOn(window, "getSelection").mockReturnValue({ toString: () => "Ahm" } as Selection);

    fireEvent.click(screen.getByText("Ahmad"));

    expect(screen.queryByText("detail page")).not.toBeInTheDocument();
    getSelection.mockRestore();
  });
});
