import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { TemplatesPage } from "./TemplatesPage";
import type { DocumentTemplate } from "./types";

const template = (over: Partial<DocumentTemplate> = {}): DocumentTemplate => ({
  id: 1,
  template_type: "eligibility_single",
  name: "Current letter",
  original_filename: "letter.docx",
  size_bytes: 20480,
  is_active: true,
  uploaded_by: 1,
  version: 2,
  created_at: "",
  ...over,
});

const rows = [
  template(),
  template({ id: 2, name: "Old letter", is_active: false, version: 5 }),
  template({ id: 3, name: "Older letter", is_active: false, version: 4 }),
];

vi.mock("@/components/ui/toaster", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("./TemplatePreviewDialog", () => ({ TemplatePreviewDialog: () => null }));
vi.mock("./templatesApi", () => ({
  // Unpaginated: the endpoint returns a plain list because the screen groups by type.
  useListTemplatesQuery: () => ({ data: rows, isLoading: false, isError: false }),
  useListTemplateTypesQuery: () => ({
    data: [
      { code: "eligibility_single", display_key: "templates.types.eligibility_single" },
      { code: "process_list", display_key: "templates.types.process_list" },
      { code: "case_summary", display_key: "templates.types.case_summary" },
    ],
  }),
}));

describe("TemplatesPage", () => {
  it("is view-only — nothing here can change a template (UC-010)", () => {
    render(<TemplatesPage />);

    for (const name of [/upload/i, /make active/i, /delete/i]) {
      expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
    }
  });

  it("shows a group for every backend type, including one with no template installed", () => {
    render(<TemplatesPage />);

    // `case_summary` was the type the frontend's own hardcoded list had fallen behind on (UC-008).
    expect(screen.getByText("Compiled case cover sheet")).toBeInTheDocument();
    expect(screen.getByText("Beneficiary list letter")).toBeInTheDocument();
  });

  it("hides retired versions behind a toggle so the active one is not buried", async () => {
    render(<TemplatesPage />);

    expect(screen.queryByText(/Old letter/)).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /show previous versions/i }));

    expect(screen.getByText(/Old letter/)).toBeInTheDocument();
    expect(screen.getByText(/Older letter/)).toBeInTheDocument();
  });
});
