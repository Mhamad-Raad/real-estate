import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DeletedPage } from "./DeletedPage";

const restoreProcessUnwrap = vi.fn().mockResolvedValue({});
const restoreProcess = vi.fn(() => ({ unwrap: restoreProcessUnwrap }));
const restoreClientUnwrap = vi.fn().mockResolvedValue({});
const restoreClient = vi.fn(() => ({ unwrap: restoreClientUnwrap }));

// The counts are the API's totals, not the page length — the whole point of the pagination fix.
const processPage = {
  count: 60,
  results: [
    { id: 7, unique_code: "A18", client_full_name: "Deleted Case", deleted_at: "2026-08-01" },
    { id: 8, unique_code: "", client_full_name: "No Code Case", deleted_at: null },
  ],
};
const clientPage = {
  count: 2,
  results: [{ id: 3, full_name: "Released Person", pid: "199001010001", deleted_at: "2026-08-01" }],
};

vi.mock("@/lib/toast", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));
vi.mock("./deletedApi", () => ({
  useListDeletedProcessesQuery: () => ({ data: processPage, isLoading: false, isError: false }),
  useListDeletedClientsQuery: () => ({ data: clientPage, isLoading: false, isError: false }),
  useRestoreProcessMutation: () => [restoreProcess, { isLoading: false }],
  useRestoreClientMutation: () => [restoreClient, { isLoading: false }],
}));

describe("DeletedPage — the admin restore desk (UC-063)", () => {
  beforeEach(() => {
    restoreProcess.mockClear();
    restoreClient.mockClear();
  });

  it("lists the deleted cases with their number", async () => {
    render(<DeletedPage />);
    expect(await screen.findByText("A18")).toBeInTheDocument();
    expect(screen.getByText("Deleted Case")).toBeInTheDocument();
    // A case opened before codes existed still has to be identifiable.
    expect(screen.getByText("No Code Case")).toBeInTheDocument();
  });

  it("counts the whole archive, not the page it is showing", async () => {
    render(<DeletedPage />);
    // 60 deleted cases across 3 pages — a tab reading "2" would be a silent cap.
    // `formatNumber` wraps its output in bidi isolates (§9), so match on the digits alone.
    expect(
      await screen.findByText((_, node) => node?.textContent?.replace(/\u2066|\u2067|\u2068|\u2069/g, "") === "60"),
    ).toBeTruthy();
  });

  it("switches to the beneficiaries released with those cases", async () => {
    render(<DeletedPage />);
    await userEvent.click(screen.getByRole("button", { name: /beneficiaries/i }));

    expect(await screen.findByText("Released Person")).toBeInTheDocument();
    expect(screen.getByText("199001010001")).toBeInTheDocument();
  });

  it("asks before restoring, and restores the row that was chosen", async () => {
    render(<DeletedPage />);
    await userEvent.click(screen.getAllByRole("button", { name: /restore/i })[0]);

    // Nothing is restored on the click alone — the confirmation is the gate.
    expect(restoreProcess).not.toHaveBeenCalled();
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: /restore/i }));

    await waitFor(() => expect(restoreProcess).toHaveBeenCalledWith(7));
    expect(restoreClient).not.toHaveBeenCalled();
  });

  it("restores a beneficiary from their own tab", async () => {
    render(<DeletedPage />);
    await userEvent.click(screen.getByRole("button", { name: /beneficiaries/i }));
    await userEvent.click(screen.getAllByRole("button", { name: /restore/i })[0]);
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: /restore/i }));

    await waitFor(() => expect(restoreClient).toHaveBeenCalledWith(3));
    expect(restoreProcess).not.toHaveBeenCalled();
  });
});