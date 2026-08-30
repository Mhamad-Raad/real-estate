import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DuplicateWarningDialog } from "./DuplicateWarningDialog";
import type { Client } from "./types";

function client(over: Partial<Client> = {}): Client {
  return {
    id: 1,
    full_name: "Test Person",
    pid: "1000",
    mother_full_name: "Test Mother",
    marital_status: "single",
    spouse_name: "",
    spouse_date_of_birth: null,
    spouse_mother_full_name: "",
  spouse_pid: "",
    is_married: false,
    date_of_birth: null,
    place_of_birth: "",
    address: "",
    phone: "",
    category: null,
    created_by: null,
    version: 1,
    created_at: "",
    ...over,
  };
}

describe("DuplicateWarningDialog (§5.7 gate)", () => {
  it("blocks saving when there is a PID-exact (hard) match", () => {
    render(
      <DuplicateWarningDialog
        open
        result={{
          pid_matches: [client({ id: 2, pid: "1000" })],
          household_matches: [],
          mother_name_matches: [],
        }}
        onProceed={() => {}}
        onClose={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: /Save anyway/i })).toBeDisabled();
  });

  it("blocks a household match and does not call it a matching National ID", () => {
    // A couple may hold one allocation, so this blocks like a PID hit — but the spouse's ID is
    // nothing like the applicant's, and saying otherwise would send the lawyer looking for a
    // number that does not exist (§5.7).
    render(
      <DuplicateWarningDialog
        open
        result={{
          pid_matches: [],
          household_matches: [client({ id: 4, full_name: "Karwan Ali", pid: "111" })],
          mother_name_matches: [],
        }}
        onProceed={() => {}}
        onClose={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: /Save anyway/i })).toBeDisabled();
    expect(screen.getByText(/Already allocated as a household/i)).toBeInTheDocument();
    expect(screen.queryByText(/Same National ID/i)).not.toBeInTheDocument();
  });

  it("allows saving when only a mother-name (soft) match exists", async () => {
    const onProceed = vi.fn();
    render(
      <DuplicateWarningDialog
        open
        result={{
          pid_matches: [],
          household_matches: [],
          mother_name_matches: [client({ id: 3, pid: "2000" })],
        }}
        onProceed={onProceed}
        onClose={() => {}}
      />,
    );
    const proceed = screen.getByRole("button", { name: /Save anyway/i });
    expect(proceed).toBeEnabled();
    await userEvent.click(proceed);
    expect(onProceed).toHaveBeenCalledTimes(1);
  });
});
