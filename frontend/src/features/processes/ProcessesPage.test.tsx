import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ProcessesPage } from "./ProcessesPage";

vi.mock("@/app/hooks", () => ({ useAppSelector: () => false }));
vi.mock("@/lib/toast", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@/hooks/useNum", () => ({ useNum: () => (n: number) => String(n) }));
vi.mock("@/features/categories/categoriesApi", () => ({
  useListCategoriesQuery: () => ({ data: [{ id: 7, code: "A", name: "A" }] }),
}));
vi.mock("./SelectionToolbar", () => ({ SelectionToolbar: () => null }));
vi.mock("./OverrideDialog", () => ({ OverrideDialog: () => null }));

const listProcesses = vi.fn();
vi.mock("./processesApi", () => ({
  useListProcessesQuery: (filters: unknown) => {
    listProcesses(filters);
    return {
      data: {
        count: 60,
        results: [
          {
            id: 3,
            unique_code: "A3",
            client_full_name: "Karwan",
            client_pid: "1",
            current_step: 2,
            overall_status: "in_progress",
            assigned_lawyer_username: "l",
            created_at: "2026-01-01",
          },
        ],
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    };
  },
  useDeleteProcessMutation: () => [vi.fn(), { isLoading: false }],
}));

// Shows where the router is and what state the last navigation carried.
function Probe() {
  const { pathname, search, state } = useLocation();
  return <div data-testid="where">{`${pathname}${search} ${JSON.stringify(state)}`}</div>;
}

// The sidebar's link: a navigation from outside the page that leaves it mounted.
function Nav() {
  const navigate = useNavigate();
  return (
    <button type="button" onClick={() => navigate("/processes")}>
      nav
    </button>
  );
}

const renderAt = (url: string) =>
  render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/processes" element={<ProcessesPage />} />
        <Route path="*" element={null} />
      </Routes>
      <Probe />
      <Nav />
    </MemoryRouter>,
  );

const lastFilters = () => listProcesses.mock.lastCall?.[0];
const url = () => screen.getByTestId("where").textContent ?? "";
const box = () => screen.getByPlaceholderText(/Search by/);

// The filters live in the URL (UC-124): the way back from a case lands on the same URL, so the
// list comes back as it was left.
describe("ProcessesPage filters in the URL", () => {
  it("reads every filter and the page from the URL", () => {
    renderAt("/processes?search=kar&category=7&status=complete&step=3&page=2");

    expect(lastFilters()).toEqual({
      search: "kar",
      category: 7,
      overall_status: "complete",
      current_step: 3,
      page: 2,
    });
    expect(box()).toHaveValue("kar");
  });

  it("keeps the page across the mount's debounced search echo", async () => {
    renderAt("/processes?search=kar&page=2");

    await new Promise((r) => setTimeout(r, 400));

    expect(url()).toBe("/processes?search=kar&page=2 null");
    expect(lastFilters().page).toBe(2);
  });

  it("writes a changed filter to the URL and returns to the first page", async () => {
    renderAt("/processes?page=2");

    await userEvent.selectOptions(screen.getByDisplayValue("All statuses"), "complete");

    expect(url()).toBe("/processes?status=complete null");
    expect(lastFilters()).toMatchObject({
      overall_status: "complete",
      page: 1,
    });
  });

  it("follows the URL when the sidebar link lands on the plain list", async () => {
    renderAt("/processes?search=kar&status=complete");

    await userEvent.click(screen.getByRole("button", { name: "nav" }));

    expect(box()).toHaveValue("");
    expect(lastFilters()).toMatchObject({ search: "", overall_status: "" });
  });

  it("keeps the space still being typed after the box's own value settles", async () => {
    renderAt("/processes");

    await userEvent.type(box(), "kar ");
    await new Promise((r) => setTimeout(r, 400));

    expect(url()).toBe("/processes?search=kar null");
    expect(box()).toHaveValue("kar ");
  });

  it("ignores a URL value that is not one of the choices", () => {
    renderAt("/processes?status=bogus&step=abc&page=-1");

    expect(lastFilters()).toMatchObject({
      overall_status: "",
      current_step: "",
      page: 1,
    });
  });

  it("sends the list URL along with the row into the case", async () => {
    renderAt("/processes?status=complete");

    await userEvent.click(screen.getByText("A3"));

    expect(url()).toBe('/processes/3 {"from":"/processes?status=complete"}');
  });
});
