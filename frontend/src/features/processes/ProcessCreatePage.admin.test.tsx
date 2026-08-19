import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ProcessCreatePage } from "./ProcessCreatePage";

// An admin, unlike the lawyer in the sibling test file, is the only role shown this field at all.
vi.mock("@/app/hooks", () => ({
  useAppSelector: () => ({ id: 3, is_admin: true }),
  useAppDispatch: () => vi.fn(),
}));
vi.mock("react-router-dom", () => ({ useNavigate: () => vi.fn() }));
vi.mock("@/lib/toast", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@/features/cardScans/ScanIntakePanel", () => ({ ScanIntakePanel: () => null }));
vi.mock("@/features/categories/categoriesApi", () => ({
  useListCategoriesQuery: () => ({ data: [{ id: 7, code: "A", name: "A" }] }),
}));
vi.mock("@/features/users/lawyersApi", () => ({
  useListLawyersQuery: () => ({
    data: [
      { id: 3, username: "admin" },
      { id: 5, username: "lawyer" },
    ],
  }),
}));
vi.mock("./processesApi", () => ({
  useCreateProcessMutation: () => [vi.fn(() => ({ unwrap: vi.fn() })), { isLoading: false }],
}));
vi.mock("@/features/clients/clientsApi", () => ({
  useCheckDuplicateMutation: () => [vi.fn(() => ({ unwrap: vi.fn() })), { isLoading: false }],
  useListClientsQuery: () => ({ data: { results: [], count: 0 }, isFetching: false }),
}));

describe("ProcessCreatePage assignee default (UC-092)", () => {
  it("starts on the admin who is opening the case, not on an empty box", () => {
    render(<ProcessCreatePage />);
    // The office opens nearly every case for themselves, and an unset box refused the submit.
    expect(screen.getByLabelText("Assigned lawyer")).toHaveValue("3");
  });
});
