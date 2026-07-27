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
        result={{ pid_matches: [client({ id: 2, pid: "1000" })], mother_name_matches: [] }}
        onProceed={() => {}}
        onClose={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: /Save anyway/i })).toBeDisabled();
  });

  it("allows saving when only a mother-name (soft) match exists", async () => {
    const onProceed = vi.fn();
    render(
      <DuplicateWarningDialog
        open
        result={{ pid_matches: [], mother_name_matches: [client({ id: 3, pid: "2000" })] }}
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
