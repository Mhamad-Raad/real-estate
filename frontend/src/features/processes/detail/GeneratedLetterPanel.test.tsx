import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { DocumentType } from "@/features/documents/documentTypesApi";

import { GeneratedLetterPanel } from "./GeneratedLetterPanel";

const unwrap = vi.fn().mockResolvedValue({ id: 1 });
const generate = vi.fn(() => ({ unwrap }));

vi.mock("@/app/hooks", () => ({ useAppDispatch: () => vi.fn(), useAppSelector: () => "token" }));
vi.mock("@/components/ui/toaster", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@/features/documents/DocumentPreview", () => ({ DocumentPreview: () => null }));
vi.mock("@/features/documents/DocumentRow", () => ({
  DocumentRow: ({ doc }: { doc: { display_filename: string } }) => <div>{doc.display_filename}</div>,
}));
vi.mock("@/features/documents/generationApi", async () => {
  const actual = await vi.importActual<typeof import("@/features/documents/generationApi")>(
    "@/features/documents/generationApi",
  );
  return {
    ...actual,
    useGenerateEligibilityMutation: () => [generate, { isLoading: false }],
    useGetGenerationJobQuery: () => ({ data: undefined }),
  };
});

const LETTER_TYPE: DocumentType = {
  code: "EligibilityLetter",
  display_key: "workflow.docType.EligibilityLetter",
  step: 1,
  required: false,
  only_when_married: false,
  generated: true,
};

const doc = (over = {}) => ({
  id: 11,
  process: 1,
  step_number: 1,
  document_type: "EligibilityLetter",
  display_filename: "letter.pdf",
  ...over,
});

function renderPanel(props: Partial<Parameters<typeof GeneratedLetterPanel>[0]> = {}) {
  return render(
    <GeneratedLetterPanel
      processId={1}
      documents={[]}
      generatedTypes={[LETTER_TYPE]}
      canGenerate
      stepComplete
      {...props}
    />,
  );
}

describe("GeneratedLetterPanel", () => {
  it("will not generate until Step 1 is complete", () => {
    // Generation is a result of finishing Step 1, never a requirement of it.
    renderPanel({ stepComplete: false });

    expect(screen.getByRole("button", { name: /generate document/i })).toBeDisabled();
    expect(screen.getByText(/finish step 1/i)).toBeInTheDocument();
  });

  it("offers generation once the step has nothing missing", () => {
    renderPanel();

    expect(screen.getByRole("button", { name: /generate document/i })).toBeEnabled();
  });

  it("offers a regenerate once a letter exists, and lists it", () => {
    renderPanel({ documents: [doc()] as never });

    expect(screen.getByText("letter.pdf")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /regenerate/i })).toBeInTheDocument();
  });

  it("shows no generate button to someone who cannot edit the case", () => {
    renderPanel({ canGenerate: false });

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
