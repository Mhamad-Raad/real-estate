import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DocumentRow } from "./DocumentRow";

// The generated-document panels show the newest file inline AND list it as a row. The row's own
// eye toggle then opened a second copy of the identical PDF underneath the first (UC-069).
vi.mock("@/app/hooks", () => ({ useAppSelector: () => "token" }));
vi.mock("@/lib/toast", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("./documentsApi", () => ({
  useDeleteDocumentMutation: () => [vi.fn(), { isLoading: false }],
}));
vi.mock("./DocumentPreview", () => ({
  DocumentPreview: () => <div data-testid="preview" />,
}));

const doc = {
  id: 1,
  display_filename: "A18_case.pdf",
  document_type: "CompiledCase",
} as never;

describe("DocumentRow preview toggle", () => {
  it("offers a preview by default", () => {
    render(<DocumentRow doc={doc} />);
    expect(screen.getByRole("button", { name: /preview/i })).toBeInTheDocument();
  });

  it("offers none when the file is already previewed beside the row", () => {
    render(<DocumentRow doc={doc} previewable={false} />);
    expect(screen.queryByRole("button", { name: /preview/i })).not.toBeInTheDocument();
    expect(screen.queryByTestId("preview")).not.toBeInTheDocument();
  });
});
