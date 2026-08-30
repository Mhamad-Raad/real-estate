import { StrictMode } from "react";

import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const fetchBlobUrl = vi.fn();
const toastError = vi.fn();

vi.mock("./download", async () => {
  const actual = await vi.importActual<typeof import("./download")>("./download");
  return {
    ...actual,
    fetchBlobUrl: (...args: unknown[]) => fetchBlobUrl(...args),
  };
});
vi.mock("@/app/hooks", () => ({ useAppSelector: () => "token" }));
vi.mock("@/lib/toast", () => ({ toast: { error: (m: string) => toastError(m) } }));

import { DocumentPreview } from "./DocumentPreview";

beforeEach(() => {
  fetchBlobUrl.mockReset();
  toastError.mockReset();
  URL.createObjectURL = vi.fn(() => "blob:x");
  URL.revokeObjectURL = vi.fn();
});

// A generated letter is deleted by the read that serves it (UC-102), so a second fetch of the same
// URL 404s and the screen reports a failure for a file that arrived perfectly. StrictMode mounts
// every effect twice in development, which is exactly how the office saw it.
describe("DocumentPreview reads a file once", () => {
  it("asks the server once under StrictMode, which runs every effect twice", async () => {
    // Rendered inside `StrictMode` deliberately — the app is (`main.tsx`), and this is the exact
    // shape of the office's report: the first read succeeds, the file is deleted by it, and the
    // second read reports a failure for a letter that arrived perfectly.
    fetchBlobUrl.mockResolvedValueOnce({ objectUrl: "blob:x", filename: "letter.pdf" });
    fetchBlobUrl.mockRejectedValue(new Error("This letter is no longer available."));

    render(
      <StrictMode>
        <DocumentPreview source={{ kind: "job", id: 7 }} title="Letter" />
      </StrictMode>,
    );

    await waitFor(() => expect(screen.getByTitle("Letter")).toBeInTheDocument());
    expect(fetchBlobUrl).toHaveBeenCalledTimes(1);
    expect(toastError).not.toHaveBeenCalled();
  });

  it("shows the server's own sentence when the file really is gone", async () => {
    fetchBlobUrl.mockRejectedValue(
      new Error("This letter is no longer available. Generate it again if needed."),
    );

    render(<DocumentPreview source={{ kind: "job", id: 8 }} title="Letter" />);

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith(
        "This letter is no longer available. Generate it again if needed.",
      ),
    );
  });
});
