import { render, screen } from "@testing-library/react";
import { MemoryRouter, Outlet } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import App from "./App";
import { useMeQuery } from "@/features/auth/authApi";

// WHICH routes sit inside `<AdminRoute>`, not whether AdminRoute works — `AdminRoute.test.tsx`
// already covers the component against a synthetic path, and that is exactly the gap that lets a
// screen be moved in or out of the guarded block unnoticed. Templates was lifted OUT of it so
// lawyers can print the blank Request form (UC-039); the other five must not have come with it.
// `vi.hoisted` because vi.mock factories are lifted above every const in the file.
const page = vi.hoisted(() => (name: string) => ({ [name]: () => <div>{name}</div> }));

vi.mock("@/components/ui/toaster", () => ({ Toaster: () => null }));
vi.mock("@/components/layout/AppLayout", () => ({ AppLayout: () => <Outlet /> }));
vi.mock("@/features/auth/ProtectedRoute", () => ({ ProtectedRoute: () => <Outlet /> }));
vi.mock("@/features/auth/authApi", () => ({ useMeQuery: vi.fn() }));
vi.mock("@/features/dashboard/DashboardPage", () => page("DashboardPage"));
vi.mock("@/features/clients/ClientsPage", () => page("ClientsPage"));
vi.mock("@/features/processes/ProcessesPage", () => page("ProcessesPage"));
vi.mock("@/features/processes/ProcessCreatePage", () => page("ProcessCreatePage"));
vi.mock("@/features/processes/detail/ProcessDetailPage", () => page("ProcessDetailPage"));
vi.mock("@/features/templates/TemplatesPage", () => page("TemplatesPage"));
vi.mock("@/features/reports/ReportsPage", () => page("ReportsPage"));
vi.mock("@/features/activities/ActivitiesPage", () => page("ActivitiesPage"));
vi.mock("@/features/categories/CategoriesPage", () => page("CategoriesPage"));
vi.mock("@/features/users/UsersPage", () => page("UsersPage"));
vi.mock("@/features/deleted/DeletedPage", () => page("DeletedPage"));
vi.mock("@/features/settings/SettingsPage", () => page("SettingsPage"));
vi.mock("@/features/auth/LoginPage", () => page("LoginPage"));
vi.mock("@/pages/NotFoundPage", () => page("NotFoundPage"));

const asLawyer = () =>
  vi.mocked(useMeQuery).mockReturnValue({ data: { is_admin: false }, isLoading: false } as never);

const goTo = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );

describe("route guarding for a lawyer", () => {
  it("lets them reach Templates — the blank Request form is printed from there", () => {
    asLawyer();
    goTo("/templates");

    expect(screen.getByText("TemplatesPage")).toBeInTheDocument();
  });

  it.each(["/reports", "/activities", "/categories", "/users", "/deleted"])(
    "still bounces them off %s",
    (path) => {
      asLawyer();
      goTo(path);

      // AdminRoute redirects to the dashboard; the admin screen must never render.
      expect(screen.getByText("DashboardPage")).toBeInTheDocument();
    },
  );
});
