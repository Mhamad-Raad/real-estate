import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { Sidebar } from "./Sidebar";

// Which screens each role is offered. The office once reported "lawyers see pages they shouldn't"
// and it could not be reproduced against anything — with no test, the split was only ever checked
// by hand. It is pinned here so a future `adminOnly` edit has to be deliberate.
let isAdmin = false;
vi.mock("@/app/hooks", () => ({
  useAppDispatch: () => vi.fn(),
  useAppSelector: (fn: (s: unknown) => unknown) =>
    fn({ auth: { user: { is_admin: isAdmin } }, ui: { sidebarCollapsed: false } }),
}));
vi.mock("./BuildStamp", () => ({ BuildStamp: () => null }));
// `uiSlice` reads `window.matchMedia` at import time to resolve the system theme, which jsdom does
// not provide. Nothing here is about theming, so the slice is stubbed rather than the browser.
vi.mock("@/features/ui/uiSlice", () => ({ toggleSidebar: () => ({ type: "ui/toggleSidebar" }) }));

const linkNames = () =>
  screen.getAllByRole("link").map((a) => a.getAttribute("href"));

const renderAs = (admin: boolean) => {
  isAdmin = admin;
  render(
    <MemoryRouter>
      <Sidebar />
    </MemoryRouter>,
  );
};

describe("Sidebar", () => {
  it("offers a lawyer their own screens plus Templates — they print the blank form (UC-039)", () => {
    renderAs(false);

    expect(linkNames()).toEqual(["/", "/clients", "/processes", "/templates", "/settings"]);
  });

  it("still keeps the management screens to admins", () => {
    renderAs(true);

    const links = linkNames();
    for (const admin of ["/reports", "/activities", "/categories", "/users", "/deleted"]) {
      expect(links).toContain(admin);
    }
  });
});
