import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TemplatesPage } from "./TemplatesPage";

// The screen makes TWO requests: the rows, and the type vocabulary. Whether a row is a blank form
// must not depend on the second one landing — when it was read from there, a slow or failed
// `/template-types/` left the office's Request form labelled "View letter" and its preview without
// the Print button, which is the only reason the entry exists (UC-039).
vi.mock("@/lib/toast", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("./TemplatePreviewDialog", () => ({ TemplatePreviewDialog: () => null }));
vi.mock("./templatesApi", () => ({
  useListTemplatesQuery: () => ({
    data: [
      {
        id: 4,
        template_type: "request_form",
        name: "request_form",
        original_filename: "request_form.pdf",
        size_bytes: 10,
        is_blank_form: true,
        is_active: true,
        uploaded_by: 1,
        version: 1,
        created_at: "",
      },
    ],
    isLoading: false,
    isError: false,
  }),
  useListTemplateTypesQuery: () => ({ data: undefined }),
}));

describe("TemplatesPage without the type vocabulary", () => {
  it("still knows the Request form is a form, not a letter", () => {
    render(<TemplatesPage />);

    expect(screen.getByRole("button", { name: /view form/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /view letter/i })).not.toBeInTheDocument();
  });
});
