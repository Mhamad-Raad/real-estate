import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { useMeQuery } from "./authApi";
import { AdminRoute } from "./AdminRoute";

// AdminRoute reads the `me` cache (not the lagging auth slice) — the regression that redirected
// admins to "/" on a full page load. These tests lock that behaviour in.
vi.mock("./authApi", () => ({ useMeQuery: vi.fn() }));
const mockMe = vi.mocked(useMeQuery);

function renderAt() {
  return render(
    <MemoryRouter initialEntries={["/admin"]}>
      <Routes>
        <Route element={<AdminRoute />}>
          <Route path="/admin" element={<div>admin area</div>} />
        </Route>
        <Route path="/" element={<div>home</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("AdminRoute", () => {
  it("renders the admin screen for an admin", () => {
    mockMe.mockReturnValue({ data: { is_admin: true }, isLoading: false } as never);
    renderAt();
    expect(screen.getByText("admin area")).toBeInTheDocument();
  });

  it("redirects a non-admin to the dashboard", () => {
    mockMe.mockReturnValue({ data: { is_admin: false }, isLoading: false } as never);
    renderAt();
    expect(screen.getByText("home")).toBeInTheDocument();
    expect(screen.queryByText("admin area")).not.toBeInTheDocument();
  });

  it("renders nothing while the profile is still loading (no premature redirect)", () => {
    mockMe.mockReturnValue({ data: undefined, isLoading: true } as never);
    renderAt();
    expect(screen.queryByText("home")).not.toBeInTheDocument();
    expect(screen.queryByText("admin area")).not.toBeInTheDocument();
  });
});
