import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ProcessDetailPage } from "./ProcessDetailPage";

// Which case the app is showing. Changed between renders to reproduce the one navigation that
// keeps this component mounted: `reapply` sends the user from /processes/A to /processes/B, and
// React Router reuses the element when only `:id` changes.
const route = { id: "1" };

vi.mock("react-router-dom", async (importOriginal) => ({
  ...(await importOriginal<typeof import("react-router-dom")>()),
  useParams: () => ({ id: route.id }),
  useNavigate: () => vi.fn(),
}));
vi.mock("@/lib/toast", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@/features/auth/authApi", () => ({ useMeQuery: () => ({ data: { id: 9, role: "admin" } }) }));
vi.mock("@/hooks/useNum", () => ({ useNum: () => (n: number) => String(n) }));

// Every panel but the two under test is noise here.
vi.mock("./InstituteStepPanel", () => ({ InstituteStepPanel: () => null }));
vi.mock("./CaseAssignee", () => ({ CaseAssignee: () => null }));
vi.mock("./LawyerNotes", () => ({ LawyerNotes: () => null }));
vi.mock("./Step1Panel", () => ({ Step1Panel: () => null }));
vi.mock("./StepProceedBar", () => ({ StepProceedBar: () => null }));
vi.mock("./Step5Panel", () => ({
  Step5Panel: ({ onCompleted }: { onCompleted: () => void }) => (
    <button type="button" onClick={onCompleted}>
      mark complete
    </button>
  ),
}));
vi.mock("./CompiledCasePanel", () => ({
  CompiledCasePanel: ({ processId, autoStart }: { processId: number; autoStart: boolean }) => (
    <span data-testid="compiled" data-process={processId} data-autostart={String(autoStart)} />
  ),
}));

const process = (id: number) => ({
  id,
  unique_code: `A${id}`,
  overall_status: "in_progress",
  current_step: 5,
  documents: [],
  client: 1,
  client_detail: { full_name: "B", pid: "P", is_married: false },
  assigned_lawyer: 9,
  steps: [1, 2, 3, 4, 5].map((n) => ({ step_number: n, status: "complete", missing: [] })),
  step_status_summary: {
    steps: { 1: "complete", 2: "complete", 3: "complete", 4: "complete", 5: "in_progress" },
    completed: 4,
    total: 5,
  },
  institute_entries: [],
  version: 1,
});

vi.mock("../processesApi", () => ({
  useGetProcessQuery: (id: number) => ({ data: process(id), isLoading: false, isError: false }),
  useCreateProcessMutation: () => [vi.fn(), { isLoading: false }],
}));

const autoStartFlag = () => screen.getByTestId("compiled").getAttribute("data-autostart");
const shownCase = () => screen.getByTestId("compiled").getAttribute("data-process");

// The compiled export runs off the press that closed the case (UC-086) — so the flag saying a
// press happened must belong to the case it happened on.
describe("ProcessDetailPage auto-compile flag", () => {
  it("does not arm the export until the case is marked complete", () => {
    route.id = "1";
    render(<ProcessDetailPage />, { wrapper: MemoryRouter });

    expect(autoStartFlag()).toBe("false");
  });

  it("arms it for the case whose button was pressed", async () => {
    route.id = "1";
    render(<ProcessDetailPage />, { wrapper: MemoryRouter });

    await userEvent.click(screen.getByRole("button", { name: /mark complete/i }));

    expect(autoStartFlag()).toBe("true");
  });

  it("does not carry the press onto the next case", async () => {
    route.id = "1";
    const { rerender } = render(<ProcessDetailPage />, { wrapper: MemoryRouter });
    await userEvent.click(screen.getByRole("button", { name: /mark complete/i }));

    // `reapply` navigates here without unmounting, so component state survives the id change.
    route.id = "2";
    rerender(<ProcessDetailPage />);

    expect(shownCase()).toBe("2");
    expect(autoStartFlag()).toBe("false");
  });
});
