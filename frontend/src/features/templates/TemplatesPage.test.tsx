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
  template({
    id: 4,
    template_type: "request_form",
    name: "request_form",
    original_filename: "request_form.pdf",
  }),
];

vi.mock("@/lib/toast", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("./TemplatePreviewDialog", () => ({ TemplatePreviewDialog: () => null }));
vi.mock("./templatesApi", () => ({
  // Unpaginated: the endpoint returns a plain list because the screen groups by type.
  useListTemplatesQuery: () => ({ data: rows, isLoading: false, isError: false }),
  useListTemplateTypesQuery: () => ({
    data: [
      { code: "eligibility_single", display_key: "templates.types.eligibility_single", blank_form: false },
      { code: "process_list", display_key: "templates.types.process_list", blank_form: false },
      { code: "case_summary", display_key: "templates.types.case_summary", blank_form: false },
      { code: "request_form", display_key: "templates.types.request_form", blank_form: true },
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

  it("lists the blank request form the office prints from here (UC-039)", () => {
    render(<TemplatesPage />);

    expect(screen.getByText("Request form (blank)")).toBeInTheDocument();
  });

  it("calls a blank form a form, not a letter — it is not something the system fills in", () => {
    render(<TemplatesPage />);

    // The letter groups keep "View letter"; only the form group is worded for a form.
    expect(screen.getAllByRole("button", { name: /view letter/i })).toHaveLength(1);
    expect(screen.getByRole("button", { name: /view form/i })).toBeInTheDocument();
  });
});
