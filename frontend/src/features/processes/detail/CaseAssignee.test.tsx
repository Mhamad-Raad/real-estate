import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ProcessDetail } from "../types";

import { CaseAssignee } from "./CaseAssignee";

const unwrap = vi.fn().mockResolvedValue({});
const reassign = vi.fn(() => ({ unwrap }));

vi.mock("../processesApi", () => ({
  useReassignProcessMutation: () => [reassign, { isLoading: false }],
}));
vi.mock("@/features/users/lawyersApi", () => ({
  useListLawyersQuery: () => ({
    data: [
      { id: 1, username: "lawyer_a" },
      { id: 2, username: "lawyer_b" },
    ],
  }),
}));
vi.mock("@/lib/toast", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

function process(over: Partial<ProcessDetail> = {}): ProcessDetail {
  return {
    id: 41,
    assigned_lawyer: 1,
    assigned_lawyer_username: "lawyer_a",
    version: 6,
    ...over,
  } as ProcessDetail;
}

describe("CaseAssignee", () => {
  it("lets an admin hand the case to another lawyer, carrying the version", async () => {
    render(<CaseAssignee process={process()} isAdmin />);

    await userEvent.selectOptions(screen.getByLabelText("Assigned lawyer"), "2");
    await userEvent.click(screen.getByRole("button", { name: "Reassign" }));

    expect(reassign).toHaveBeenCalledWith({ id: 41, assigned_lawyer: 2, version: 6 });
  });

  it("keeps the button disabled while the current assignee is selected", () => {
    render(<CaseAssignee process={process()} isAdmin />);
    expect(screen.getByRole("button", { name: "Reassign" })).toBeDisabled();
  });

  it("shows a lawyer the owner as plain text, with no control to change it", () => {
    render(<CaseAssignee process={process()} isAdmin={false} />);

    expect(screen.getByText("lawyer_a")).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reassign" })).not.toBeInTheDocument();
  });
});
