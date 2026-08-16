import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { DocumentType } from "@/features/documents/documentTypesApi";
import type { DocumentMeta } from "@/features/documents/types";

import { StepDocumentSlots } from "./StepDocumentSlots";
import type { ProcessDetail } from "../types";

const CARD: DocumentType = {
  code: "ClientID",
  display_key: "workflow.docType.ClientID",
  step: 1,
  required: true,
  only_when_married: false,
  generated: false,
  expected_parts: 2,
  counts_pages: true,
};
const PAPERS: DocumentType = { ...CARD, code: "RealEstate", counts_pages: false };

vi.mock("@/features/documents/DocumentRow", () => ({ DocumentRow: () => null }));
vi.mock("@/features/documents/DocumentUpload", () => ({ DocumentUpload: () => null }));
vi.mock("@/features/documents/documentTypesApi", () => ({
  useListDocumentTypesQuery: () => ({ data: [CARD, PAPERS] }),
}));
// The real hook renders Arabic-Indic digits wrapped in bidi isolates, which would make every
// assertion below a regex about invisible characters.
vi.mock("@/hooks/useNum", () => ({ useNum: () => (n: number) => String(n) }));

const doc = (over: Partial<DocumentMeta>): DocumentMeta =>
  ({ id: 1, step_number: 1, document_type: "ClientID", page_count: 1, ...over }) as DocumentMeta;

const process = (documents: DocumentMeta[]) =>
  ({ id: 1, documents, client_detail: { is_married: false } }) as unknown as ProcessDetail;

// The slot's count answers one question: is this paper complete? (UC-083, UC-084)
describe("StepDocumentSlots count", () => {
  it("counts both sides of a card stored as one two-page file", () => {
    render(<StepDocumentSlots process={process([doc({ page_count: 2 })])} step={1} canEdit />);

    expect(screen.getByText("2 of 2 sides")).toBeInTheDocument();
  });

  it("never reports more sides than the card has", () => {
    // A three-page scan read "3 of 2 sides", which looks like a fault rather than an answer.
    render(<StepDocumentSlots process={process([doc({ page_count: 3 })])} step={1} canEdit />);

    expect(screen.getByText("2 of 2 sides")).toBeInTheDocument();
  });

  it("still shows a half-filed card as incomplete", () => {
    render(<StepDocumentSlots process={process([doc({ page_count: 1 })])} step={1} canEdit />);

    expect(screen.getByText("1 of 2 sides")).toBeInTheDocument();
  });

  it("counts files, not pages, for a paper the office files twice", () => {
    // Two separate papers, one of which runs to three pages — that is 2 of 2 files, not 4.
    const papers = [
      doc({ id: 2, document_type: "RealEstate", page_count: 3 }),
      doc({ id: 3, document_type: "RealEstate", page_count: 1 }),
    ];

    render(<StepDocumentSlots process={process(papers)} step={1} canEdit />);

    expect(screen.getByText("2 of 2 files")).toBeInTheDocument();
  });
});
