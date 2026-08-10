import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { TemplatePreviewDialog } from "./TemplatePreviewDialog";
import type { DocumentTemplate } from "./types";

const downloadTemplatePreview = vi.fn().mockResolvedValue(undefined);

vi.mock("@/lib/toast", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@/app/hooks", () => ({ useAppSelector: () => "token" }));
vi.mock("@/features/documents/download", () => ({
  fetchTemplatePreviewUrl: () => Promise.resolve("blob:preview"),
  downloadTemplatePreview: (...args: unknown[]) => downloadTemplatePreview(...args),
}));

const form: DocumentTemplate = {
  id: 7,
  template_type: "request_form",
  name: "request_form",
  original_filename: "request_form.pdf",
  size_bytes: 1779843,
  is_blank_form: true,
  is_active: true,
  uploaded_by: 1,
  version: 1,
  created_at: "",
};

describe("TemplatePreviewDialog", () => {
  it("can print and download — a blank form exists to leave this screen on paper (UC-039)", async () => {
    render(<TemplatePreviewDialog template={form} onClose={() => {}} />);

    // Both start disabled until the bytes arrive; the office must never print an empty frame.
    const download = await screen.findByRole("button", { name: /download/i });
    await waitFor(() => expect(download).toBeEnabled());
    expect(screen.getByRole("button", { name: /print/i })).toBeEnabled();

    await userEvent.click(download);

    expect(downloadTemplatePreview).toHaveBeenCalledWith(7, "request_form.pdf", "token");
  });

  it("tells the office what to do with it, not that it is a sample-data letter", async () => {
    render(<TemplatePreviewDialog template={form} onClose={() => {}} />);

    expect(await screen.findByText(/have it signed/i)).toBeInTheDocument();
    expect(screen.queryByText(/sample/i)).not.toBeInTheDocument();
  });

  it("offers neither on a LETTER — its preview is sample data and must not reach paper", async () => {
    render(<TemplatePreviewDialog
        template={{ ...form, template_type: "eligibility_single", is_blank_form: false }}
        onClose={() => {}}
      />);

    expect(await screen.findByText(/sample values/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /download/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /print/i })).not.toBeInTheDocument();
  });
});
