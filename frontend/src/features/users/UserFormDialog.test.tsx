import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { UserFormDialog } from "./UserFormDialog";
import type { AdminUser } from "./types";

// The argument is declared so `mock.calls[0][0]` is readable — an untyped `vi.fn(() => …)` types
// the call tuple as `[]` and only the build catches it (see the repo's tooling notes).
type UserArgs = Record<string, unknown>;
const createUnwrap = vi.fn().mockResolvedValue({ id: 9 });
const create = vi.fn((_args: UserArgs) => ({ unwrap: createUnwrap }));
const updateUnwrap = vi.fn().mockResolvedValue({ id: 3 });
const update = vi.fn((_args: UserArgs) => ({ unwrap: updateUnwrap }));

vi.mock("@/lib/toast", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("./usersApi", () => ({
  useCreateUserMutation: () => [create, { isLoading: false }],
  useUpdateUserMutation: () => [update, { isLoading: false }],
}));

const EXISTING: AdminUser = {
  id: 3,
  username: "lawyer1",
  first_name: "A",
  last_name: "B",
  email: "a@b.c",
  role: "lawyer",
  is_admin: false,
  version: 1,
} as AdminUser;

const fill = async (password: string, confirm: string) => {
  await userEvent.type(screen.getByLabelText(/New password|^Password$/), password);
  await userEvent.type(screen.getByLabelText(/Confirm password/), confirm);
};

// A mistyped password creates an account nobody can sign into, and these machines have no internet
// and no password reset — so the two fields must be proven to gate the request (UC-077).
describe("UserFormDialog password section", () => {
  beforeEach(() => {
    create.mockClear();
    update.mockClear();
  });

  it("refuses to submit when the two passwords differ", async () => {
    render(<UserFormDialog open user={EXISTING} onClose={vi.fn()} />);

    await fill("correct-horse-1", "correct-horse-2");
    await userEvent.click(screen.getByRole("button", { name: /Save/ }));

    expect(update).not.toHaveBeenCalled();
    expect(screen.getByText(/do not match/i)).toBeInTheDocument();
  });

  it("sends the password once the confirmation matches", async () => {
    render(<UserFormDialog open user={EXISTING} onClose={vi.fn()} />);

    await fill("correct-horse-1", "correct-horse-1");
    await userEvent.click(screen.getByRole("button", { name: /Save/ }));

    expect(update).toHaveBeenCalledWith(expect.objectContaining({ password: "correct-horse-1" }));
  });

  it("leaves the password alone when both fields are left blank on an edit", async () => {
    render(<UserFormDialog open user={EXISTING} onClose={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: /Save/ }));

    expect(update).toHaveBeenCalledTimes(1);
    expect(update.mock.calls[0][0]).not.toHaveProperty("password");
  });

  it("hides the password again as soon as the eye is released", async () => {
    render(<UserFormDialog open user={EXISTING} onClose={vi.fn()} />);
    const input = screen.getByLabelText(/New password/) as HTMLInputElement;
    const eye = screen.getAllByRole("button", { name: /Hold to show/ })[0];

    // Driven with raw pointer events: the point of the control is that reveal lasts exactly as
    // long as the press, which is a property of down/up, not of a click.
    expect(input.type).toBe("password");
    fireEvent.pointerDown(eye);
    expect(input.type).toBe("text");
    fireEvent.pointerUp(eye);
    expect(input.type).toBe("password");
  });
});
