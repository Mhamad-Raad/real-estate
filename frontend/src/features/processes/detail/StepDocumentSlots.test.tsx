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
  name_ckb: "ناسنامەی کڕیار",
  name_en: "", // one label is enough for a card
};
// The one paper the office knows by both names, so its slot prints the pair (UC-088).
const PAPERS: DocumentType = {
  ...CARD,
  code: "RealEstate",
  counts_pages: false,
  name_ckb: "فۆرم و نووسراوی شارەوانی",
  name_en: "Municipality form and letter",
};

vi.mock("@/features/documents/DocumentRow", () => ({ DocumentRow: () => null }));
// Rendered as a marker rather than dropped, so a test can ask whether the slot still takes a file.
vi.mock("@/features/documents/DocumentUpload", () => ({
  DocumentUpload: ({ documentType, disabled }: { documentType: string; disabled?: boolean }) => (
    <span data-testid={`upload-${documentType}`} data-disabled={String(Boolean(disabled))} />
  ),
}));
// Only the query is faked — `documentTypeLabel` is the real one, so what the slot prints is
// tested rather than restated.
vi.mock("@/features/documents/documentTypesApi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/documents/documentTypesApi")>()),
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

// The office knows the Step-4 paper by a name the English label does not carry (UC-088).
describe("StepDocumentSlots label", () => {
  it("prints both names for a paper that has an English one of its own", () => {
    render(<StepDocumentSlots process={process([])} step={1} canEdit />);

    expect(
      screen.getByText(/Municipality form and letter — فۆرم و نووسراوی شارەوانی/),
    ).toBeInTheDocument();
  });

  it("leaves a slot with one name alone", () => {
    render(<StepDocumentSlots process={process([])} step={1} canEdit />);

    // The card's translated label stands on its own — pairing every slot would be noise.
    expect(screen.queryByText(/ناسنامەی کڕیار/)).not.toBeInTheDocument();
  });
});

// A full slot takes nothing more (UC-085) — the office was able to add a third and fourth side.
describe("StepDocumentSlots capacity", () => {
  const uploadDisabled = (type: string) =>
    screen.getByTestId(`upload-${type}`).getAttribute("data-disabled");

  it("still takes a file while the card has room", () => {
    render(<StepDocumentSlots process={process([doc({ page_count: 1 })])} step={1} canEdit />);

    expect(uploadDisabled("ClientID")).toBe("false");
  });

  it("takes nothing once both sides are on file", () => {
    render(<StepDocumentSlots process={process([doc({ page_count: 2 })])} step={1} canEdit />);

    expect(uploadDisabled("ClientID")).toBe("true");
  });

  it("closes a slot that is already over capacity on an older case", () => {
    render(<StepDocumentSlots process={process([doc({ page_count: 3 })])} step={1} canEdit />);

    expect(uploadDisabled("ClientID")).toBe("true");
  });

  it("closes each slot on its own count", () => {
    const papers = [doc({ page_count: 2 }), doc({ id: 2, document_type: "RealEstate" })];

    render(<StepDocumentSlots process={process(papers)} step={1} canEdit />);

    expect(uploadDisabled("ClientID")).toBe("true");
    expect(uploadDisabled("RealEstate")).toBe("false"); // 1 of 2 papers
  });
});
