import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FastEntryPage } from "./FastEntryPage";

const unwrap = vi.fn().mockResolvedValue({ id: 42, unique_code: "A34" });
const fastEntry = vi.fn(() => ({ unwrap }));
const toastError = vi.fn();

const navigate = vi.fn();
vi.mock("react-router-dom", () => ({ useNavigate: () => navigate }));
vi.mock("@/lib/toast", () => ({ toast: { success: vi.fn(), error: (m: string) => toastError(m) } }));
vi.mock("@/features/categories/categoriesApi", () => ({
  useListCategoriesQuery: () => ({ data: [{ id: 7, code: "A", name: "A" }] }),
}));
vi.mock("./processesApi", () => ({
  useFastEntryProcessMutation: () => [fastEntry, { isLoading: false }],
}));
const clean = { pid_matches: [], household_matches: [], mother_name_matches: [] };
const checkUnwrap = vi.fn().mockResolvedValue(clean);
vi.mock("@/features/clients/clientsApi", () => ({
  useCheckDuplicateMutation: () => [() => ({ unwrap: checkUnwrap }), { isLoading: false }],
}));

const pdf = () => new File(["%PDF-1.4"], "case.pdf", { type: "application/pdf" });

// jsdom has no object URLs; the page makes one per picked file for the preview.
const revoked: string[] = [];
let blobN = 0;
vi.stubGlobal("URL", {
  ...URL,
  createObjectURL: () => `blob:${blobN++}`,
  revokeObjectURL: (url: string) => revoked.push(url),
});

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

const submit = () => userEvent.click(screen.getByRole("button", { name: "Save" }));

beforeEach(() => {
  fastEntry.mockClear();
  unwrap.mockClear();
  toastError.mockClear();
  navigate.mockClear();
  checkUnwrap.mockResolvedValue(clean);
  revoked.length = 0;
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

  it("warns about a similar mother's name, and files it when the lawyer continues", async () => {
    // The office asked for the same warning the intake form gives (2026-08-30). It is advisory —
    // almost always a sibling — so it must not block; and on a backlog case it would otherwise
    // surface only inside Step 1, which nobody opens.
    checkUnwrap.mockResolvedValueOnce({
      ...clean,
      mother_name_matches: [{ id: 9, full_name: "Sibling Person", pid: "197712120001" }],
    });
    render(<FastEntryPage />);
    await fill();

    await submit();
    expect(await screen.findByText("Sibling Person")).toBeInTheDocument();
    expect(fastEntry).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: /Save anyway|Continue|Proceed/i }));

    expect(fastEntry).toHaveBeenCalled();
  });

  it("does not file when the lawyer cancels the warning", async () => {
    checkUnwrap.mockResolvedValueOnce({
      ...clean,
      mother_name_matches: [{ id: 9, full_name: "Sibling Person", pid: "197712120001" }],
    });
    render(<FastEntryPage />);
    await fill();

    await submit();
    // The dialog's × carries the same label as its footer button; the footer one is last.
    await userEvent.click(screen.getAllByRole("button", { name: "Cancel" }).at(-1)!);

    expect(fastEntry).not.toHaveBeenCalled();
  });

  it("goes back to the list, where the case it just made is now visible", async () => {
    // The office's call (2026-08-30): they wanted to see the case land, with its code, before
    // starting the next one.
    render(<FastEntryPage />);
    await fill();

    await submit();

    expect(navigate).toHaveBeenCalledWith("/processes");
  });

  it("stays put when the save failed, so nothing typed is lost", async () => {
    unwrap.mockRejectedValueOnce({ status: 400, data: { pid: ["Must be digits."] } });
    render(<FastEntryPage />);
    await fill();

    await submit();

    expect(navigate).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Full name")).toHaveValue("Karwan Ahmed");
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

  it("shows the picked PDF back, so the wrong file is caught before it is filed", async () => {
    render(<FastEntryPage />);

    await userEvent.upload(screen.getByLabelText(/Case file/), pdf());

    expect(screen.getByTitle("case.pdf")).toHaveAttribute("src", expect.stringMatching(/^blob:/));
    expect(screen.getByText("case.pdf")).toBeInTheDocument();
    expect(screen.getByText(/1 KB/)).toBeInTheDocument();
  });

  it("previews a picked image as an image", async () => {
    render(<FastEntryPage />);

    const jpeg = new File(["x"], "case.jpg", { type: "image/jpeg" });
    await userEvent.upload(screen.getByLabelText(/Case file/), jpeg);

    expect(screen.getByAltText("case.jpg")).toHaveAttribute("src", expect.stringMatching(/^blob:/));
  });

  it("says so for a scanner TIFF instead of showing a blank frame", async () => {
    render(<FastEntryPage />);

    const tiff = new File(["II*"], "scan.tif", { type: "image/tiff" });
    await userEvent.upload(screen.getByLabelText(/Case file/), tiff);

    expect(screen.getByText(/No preview for this file type/)).toBeInTheDocument();
    // The name and size are the check that remains, so they must still be there.
    expect(screen.getByText("scan.tif")).toBeInTheDocument();
  });

  it("releases the old preview when the file is replaced", async () => {
    render(<FastEntryPage />);
    const input = screen.getByLabelText(/Case file/);

    await userEvent.upload(input, pdf());
    const first = screen.getByTitle("case.pdf").getAttribute("src");
    await userEvent.upload(input, new File(["x"], "other.jpg", { type: "image/jpeg" }));

    expect(revoked).toContain(first);
  });
});
