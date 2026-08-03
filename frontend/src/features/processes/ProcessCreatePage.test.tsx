import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ProcessCreatePage } from "./ProcessCreatePage";

const createUnwrap = vi.fn().mockResolvedValue({ id: 42 });
const create = vi.fn(() => ({ unwrap: createUnwrap }));

// The household rule is the one dedup rule no DB index can express (§5.7 — "no row's pid may equal
// any other row's spouse_pid" is cross-row), so this gate is the only thing holding it.
const householdHit = {
  pid_matches: [],
  household_matches: [
    { id: 9, full_name: "Already Allocated", pid: "199001019999" },
  ],
  mother_name_matches: [],
};
const clean = { pid_matches: [], household_matches: [], mother_name_matches: [] };

const checkUnwrap = vi.fn().mockResolvedValue(clean);
const checkDuplicate = vi.fn(() => ({ unwrap: checkUnwrap }));

vi.mock("@/app/hooks", () => ({
  useAppSelector: () => ({ id: 1, is_admin: false }),
  useAppDispatch: () => vi.fn(),
}));
vi.mock("react-router-dom", () => ({ useNavigate: () => vi.fn() }));
vi.mock("@/components/ui/toaster", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@/features/cardScans/ScanIntakePanel", () => ({ ScanIntakePanel: () => null }));
vi.mock("@/features/categories/categoriesApi", () => ({
  useListCategoriesQuery: () => ({ data: [] }),
}));
vi.mock("@/features/users/lawyersApi", () => ({
  useListLawyersQuery: () => ({ data: [] }),
}));
vi.mock("./processesApi", () => ({
  useCreateProcessMutation: () => [create, { isLoading: false }],
}));
vi.mock("@/features/clients/clientsApi", () => ({
  useCheckDuplicateMutation: () => [checkDuplicate, { isLoading: false }],
  useListClientsQuery: () => ({ data: { results: [], count: 0 }, isFetching: false }),
}));

async function fillManualForm() {
  await userEvent.click(screen.getByRole("button", { name: /enter manually/i }));
  await userEvent.type(screen.getByLabelText("Full name"), "Test Person");
  await userEvent.type(screen.getByLabelText("National ID"), "200001011234");
  await userEvent.type(screen.getByLabelText("Mother's full name"), "Test Mother");
  await userEvent.type(screen.getByLabelText("Date of birth"), "1990-01-01");
}

describe("ProcessCreatePage duplicate gate (UC-027)", () => {
  it("checks for duplicates before creating anything", async () => {
    checkUnwrap.mockResolvedValueOnce(clean);
    render(<ProcessCreatePage />);
    await fillManualForm();

    await userEvent.click(screen.getByRole("button", { name: /create case/i }));

    expect(checkDuplicate).toHaveBeenCalledWith(
      expect.objectContaining({ pid: "200001011234", mother_full_name: "Test Mother" }),
    );
    expect(create).toHaveBeenCalled();
  });

  it("blocks the submit on a household match and creates nothing", async () => {
    checkUnwrap.mockResolvedValueOnce(householdHit);
    create.mockClear();
    render(<ProcessCreatePage />);
    await fillManualForm();

    await userEvent.click(screen.getByRole("button", { name: /create case/i }));

    // The warning is shown, and the case is NOT created while it is unresolved.
    expect(await screen.findByText("Already Allocated")).toBeInTheDocument();
    expect(create).not.toHaveBeenCalled();
  });

  it("does not wave a possible duplicate through when the check itself fails", async () => {
    checkUnwrap.mockRejectedValueOnce(new Error("offline"));
    create.mockClear();
    render(<ProcessCreatePage />);
    await fillManualForm();

    await userEvent.click(screen.getByRole("button", { name: /create case/i }));

    expect(create).not.toHaveBeenCalled();
  });
});
