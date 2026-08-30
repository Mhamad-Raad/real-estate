import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FastEntryPage } from "./FastEntryPage";

const unwrap = vi.fn().mockResolvedValue({ id: 42, unique_code: "A34" });
const fastEntry = vi.fn(() => ({ unwrap }));
const toastError = vi.fn();

vi.mock("react-router-dom", () => ({ useNavigate: () => vi.fn() }));
vi.mock("@/lib/toast", () => ({ toast: { success: vi.fn(), error: (m: string) => toastError(m) } }));
vi.mock("@/features/categories/categoriesApi", () => ({
  useListCategoriesQuery: () => ({ data: [{ id: 7, code: "A", name: "A" }] }),
}));
vi.mock("./processesApi", () => ({
  useFastEntryProcessMutation: () => [fastEntry, { isLoading: false }],
}));

const pdf = () => new File(["%PDF-1.4"], "case.pdf", { type: "application/pdf" });

async function fill({ withFile = true } = {}) {
  await userEvent.type(screen.getByLabelText("Full name"), "Karwan Ahmed");
  await userEvent.type(screen.getByLabelText("National ID"), "197712120099");
  await userEvent.type(screen.getByLabelText("Mother's full name"), "Nask Ali");
  // The day box carries the field's own label, so it is named "Date of birth" here; only the
  // other two fall back to naming themselves.
  await userEvent.type(screen.getByLabelText("Date of birth"), "12");
  await userEvent.type(screen.getByLabelText("Month"), "12");
  await userEvent.type(screen.getByLabelText("Year"), "1977");
  await userEvent.selectOptions(screen.getByLabelText("Category"), "7");
  await userEvent.type(screen.getByLabelText("Land ID"), "4472");
  if (withFile) await userEvent.upload(screen.getByLabelText(/Case file/), pdf());
}

const submit = () => userEvent.click(screen.getByRole("button", { name: /Save and start the next/ }));

beforeEach(() => {
  fastEntry.mockClear();
  unwrap.mockClear();
  toastError.mockClear();
});

describe("FastEntryPage", () => {
  it("sends the findable fields and the one PDF together", async () => {
    render(<FastEntryPage />);
    await fill();

    await submit();

    expect(fastEntry).toHaveBeenCalledWith(
      expect.objectContaining({
        full_name: "Karwan Ahmed",
        pid: "197712120099",
        mother_full_name: "Nask Ali",
        date_of_birth: "1977-12-12",
        category: "7",
        land_id: "4472",
        file: expect.any(File),
      }),
    );
  });

  it("marks the case finished by default, since the backlog is finished cases", async () => {
    render(<FastEntryPage />);
    await fill();

    await submit();

    expect(fastEntry).toHaveBeenCalledWith(expect.objectContaining({ mark_complete: true }));
  });

  it("leaves one open when the office says its paperwork is not", async () => {
    render(<FastEntryPage />);
    await fill();

    await userEvent.click(screen.getByRole("checkbox"));
    await submit();

    expect(fastEntry).toHaveBeenCalledWith(expect.objectContaining({ mark_complete: false }));
  });

  it("will not send without the case file", async () => {
    render(<FastEntryPage />);
    await fill({ withFile: false });

    await submit();

    expect(fastEntry).not.toHaveBeenCalled();
    expect(toastError).toHaveBeenCalled();
  });

  it("empties itself for the next one rather than navigating away", async () => {
    // The office types these in runs of hundreds; landing on the case just created would mean
    // navigating back for every single one.
    render(<FastEntryPage />);
    await fill();

    await submit();

    expect(screen.getByLabelText("Full name")).toHaveValue("");
    expect(screen.getByLabelText("National ID")).toHaveValue("");
  });

  it("keeps the category, which is the one thing a run of cases shares", async () => {
    render(<FastEntryPage />);
    await fill();

    await submit();

    expect(screen.getByLabelText("Category")).toHaveValue("7");
  });

  it("filters the national ID as it is typed, like every other ID box", async () => {
    render(<FastEntryPage />);

    await userEvent.type(screen.getByLabelText("National ID"), "١٩٧٧a12");

    expect(screen.getByLabelText("National ID")).toHaveValue("197712");
  });

  it("marks the field the server rejected", async () => {
    unwrap.mockRejectedValueOnce({ status: 400, data: { pid: ["Must be 12 digits."] } });
    render(<FastEntryPage />);
    await fill();

    await submit();

    expect(await screen.findByText("Must be 12 digits.")).toBeInTheDocument();
  });
});
