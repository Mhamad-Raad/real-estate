import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Client } from "@/features/clients/types";

import { ClientDetailsPanel } from "./ClientDetailsPanel";

const unwrap = vi.fn().mockResolvedValue({});
const updateClient = vi.fn(() => ({ unwrap }));

vi.mock("@/features/clients/clientsApi", () => ({
  useUpdateClientMutation: () => [updateClient, { isLoading: false }],
}));
// The panel renders the shared `ClientFields`, which calls this hook even when the category select
// is hidden — an RTK Query hook still needs a store when it is skipped.
vi.mock("@/features/categories/categoriesApi", () => ({
  useListCategoriesQuery: () => ({ data: [] }),
}));
vi.mock("@/lib/toast", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

function client(over: Partial<Client> = {}): Client {
  return {
    id: 7,
    full_name: "Test Person",
    pid: "1000",
    mother_full_name: "Test Mother",
    marital_status: "single",
    spouse_name: "",
    spouse_date_of_birth: null,
    spouse_mother_full_name: "",
  spouse_pid: "",
    is_married: false,
    date_of_birth: "1990-01-01",
    place_of_birth: "",
    address: "",
    phone: "",
    category: null,
    created_by: null,
    version: 3,
    created_at: "",
    ...over,
  };
}

describe("ClientDetailsPanel", () => {
  it("hides the spouse block until the client is married", async () => {
    render(<ClientDetailsPanel client={client()} canEdit />);
    expect(screen.queryByLabelText("Spouse name")).not.toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText("Marital status"), "married");

    expect(screen.getByLabelText("Spouse name")).toBeInTheDocument();
    expect(screen.getByLabelText("Spouse date of birth")).toBeInTheDocument();
    expect(screen.getByLabelText("Spouse's mother's full name")).toBeInTheDocument();
  });

  it("keeps save disabled until every spouse field is filled", async () => {
    render(<ClientDetailsPanel client={client()} canEdit />);
    await userEvent.selectOptions(screen.getByLabelText("Marital status"), "married");
    const save = screen.getByRole("button", { name: /save beneficiary details/i });

    // The server requires the three together — offering the save would only earn a 400.
    await userEvent.type(screen.getByLabelText("Spouse name"), "Partner");
    expect(save).toBeDisabled();

    await userEvent.type(screen.getByLabelText("Spouse date of birth"), "1992-02-02");
    expect(save).toBeDisabled();

    await userEvent.type(screen.getByLabelText("Spouse's mother's full name"), "Partner Mother");
    expect(save).toBeEnabled();
  });

  it("blanks the spouse details when the client is no longer married", async () => {
    const married = client({
      marital_status: "married",
      spouse_name: "Partner",
      spouse_date_of_birth: "1992-02-02",
      spouse_mother_full_name: "Partner Mother",
      is_married: true,
    });
    render(<ClientDetailsPanel client={married} canEdit />);

    await userEvent.selectOptions(screen.getByLabelText("Marital status"), "divorced");
    await userEvent.click(screen.getByRole("button", { name: /save beneficiary details/i }));

    expect(updateClient).toHaveBeenCalledWith(
      expect.objectContaining({
        id: 7,
        version: 3,
        marital_status: "divorced",
        spouse_name: "",
        spouse_date_of_birth: null,
        spouse_mother_full_name: "",
      }),
    );
  });

  it("offers no save button to a lawyer who cannot edit", () => {
    render(<ClientDetailsPanel client={client()} canEdit={false} />);

    expect(
      screen.queryByRole("button", { name: /save beneficiary details/i }),
    ).not.toBeInTheDocument();
  });
});
