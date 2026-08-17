import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DocumentUpload } from "./DocumentUpload";

vi.mock("@/lib/toast", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("./ScanDocumentDialog", () => ({ ScanDocumentDialog: () => null }));
vi.mock("./documentsApi", () => ({
  useUploadDocumentMutation: () => [vi.fn(), { isLoading: false }],
}));

describe("DocumentUpload", () => {
  it("offers every format the server converts, not PDF alone", () => {
    // The office's scanner delivers JPEG/TIFF and the API accepts both, but the picker listed
    // only PDFs — so their own scan was not selectable (UC-087).
    const { container } = render(<DocumentUpload process={1} step={1} documentType="ClientID" />);

    expect(container.querySelector("input[type=file]")?.getAttribute("accept")).toBe(
      "application/pdf,image/jpeg,image/png,image/tiff",
    );
  });

  it("explains a control it has greyed out", () => {
    const { container } = render(
      <DocumentUpload process={1} step={1} documentType="ClientID" disabled disabledReason="Full" />,
    );

    expect(container.querySelector("[title='Full']")).toBeInTheDocument();
  });
});
