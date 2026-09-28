import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SpouseSection } from "./SpouseSection";
import { EMPTY_SPOUSE } from "./spouseFields";

vi.mock("@/app/hooks", () => ({ useAppDispatch: () => vi.fn(), useAppSelector: () => "token" }));
vi.mock("@/lib/toast", () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));

const fetchMock = vi.fn().mockResolvedValue({ ok: true, blob: async () => new Blob(["%PDF-"]) });

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("URL", { ...URL, createObjectURL: () => "blob:x", revokeObjectURL: () => {} });
  fetchMock.mockClear();
});

describe("SpouseSection", () => {
  it("shows the spouse's own card beside the spouse's fields (UC-128)", async () => {
    render(<SpouseSection scanId={9} scan={null} reading values={EMPTY_SPOUSE} onChange={vi.fn()} />);

    expect(screen.getByRole("heading", { name: /spouse's card/ })).toBeInTheDocument();
    expect(await screen.findByTitle("The scanned card")).toBeInTheDocument();
    expect(String(fetchMock.mock.calls[0][0])).toContain("/card-scans/9/file/");
  });

  it("asks for the spouse's birth date day / month / year", () => {
    render(<SpouseSection scanId={null} scan={null} reading={false} values={EMPTY_SPOUSE} onChange={vi.fn()} />);

    expect(screen.getByLabelText("Month")).toBeInTheDocument();
    expect(screen.getByLabelText("Year")).toBeInTheDocument();
  });
});

describe("SpouseSection keystroke rules", () => {
  it("refuses a digit in a spouse name and holds the ID to digits, as the beneficiary's boxes do", async () => {
    const onChange = vi.fn();
    render(<SpouseSection scanId={null} scan={null} reading={false} values={EMPTY_SPOUSE} onChange={onChange} />);

    await userEvent.type(screen.getByLabelText(/Spouse's full name/), "4");
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ spouse_name: "" }));

    await userEvent.type(screen.getByLabelText(/Spouse's card number/), "x");
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ spouse_pid: "" }));
    expect(screen.getByLabelText(/Spouse's card number/)).toHaveAttribute("dir", "ltr");
  });
});
