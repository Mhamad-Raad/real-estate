import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { TemplatesPage } from "./TemplatesPage";
import type { DocumentTemplate } from "./types";

const activateUnwrap = vi.fn().mockResolvedValue({});
const activate = vi.fn(() => ({ unwrap: activateUnwrap }));
const remove = vi.fn(() => ({ unwrap: vi.fn().mockResolvedValue({}) }));

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

const rows = [template(), template({ id: 2, name: "Old letter", is_active: false, version: 5 })];

vi.mock("@/components/ui/toaster", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("./TemplateUploadDialog", () => ({ TemplateUploadDialog: () => null }));
vi.mock("./templatesApi", () => ({
  useListTemplatesQuery: () => ({
    data: { results: rows, count: rows.length },
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  }),
  useActivateTemplateMutation: () => [activate, { isLoading: false }],
  useDeleteTemplateMutation: () => [remove, { isLoading: false }],
}));

describe("TemplatesPage", () => {
  it("marks which template is currently in use", () => {
    render(<TemplatesPage />);

    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("Retired")).toBeInTheDocument();
  });

  it("offers activation only for a template that is not already active", () => {
    render(<TemplatesPage />);

    // One row is active, so exactly one "make active" action should exist.
    expect(screen.getAllByRole("button", { name: /make active/i })).toHaveLength(1);
  });

  it("activates with the optimistic-lock version of that row", async () => {
    render(<TemplatesPage />);

    await userEvent.click(screen.getByRole("button", { name: /make active/i }));

    expect(activate).toHaveBeenCalledWith({ id: 2, version: 5 });
  });
});
