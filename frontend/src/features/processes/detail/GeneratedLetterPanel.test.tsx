import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { GeneratedLetterPanel } from "./GeneratedLetterPanel";

const unwrap = vi.fn().mockResolvedValue({ id: 7 });
const generate = vi.fn((_args: { process: number }) => ({ unwrap }));
// Set per test: what polling the started job reports back.
let job: { id: number; status: string; error: string } | undefined;

vi.mock("@/app/hooks", () => ({ useAppDispatch: () => vi.fn(), useAppSelector: () => "token" }));
vi.mock("@/lib/toast", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@/features/documents/DocumentPreview", () => ({
  DocumentPreview: ({ source }: { source: { kind: string; id: number } }) => (
    <div data-testid="preview">{`${source.kind}:${source.id}`}</div>
  ),
}));
vi.mock("@/features/documents/generationApi", async () => {
  const actual = await vi.importActual<typeof import("@/features/documents/generationApi")>(
    "@/features/documents/generationApi",
  );
  return {
    ...actual,
    useGenerateEligibilityMutation: () => [generate, { isLoading: false }],
    // `skip` must be honoured, or the panel reports a finished job before anything was started.
    useGetGenerationJobQuery: (_id: number, opts?: { skip?: boolean }) => ({
      data: opts?.skip ? undefined : job,
    }),
  };
});

function renderPanel(props: Partial<Parameters<typeof GeneratedLetterPanel>[0]> = {}) {
  return render(<GeneratedLetterPanel processId={1} canGenerate hasNames {...props} />);
}

describe("GeneratedLetterPanel", () => {
  beforeEach(() => {
    job = undefined;
    generate.mockClear();
  });

  it("will not generate before the beneficiary has a name", () => {
    // The letter renders names; without them it would print an empty form (UC-038).
    renderPanel({ hasNames: false });

    expect(screen.getByRole("button", { name: /generate document/i })).toBeDisabled();
  });

  it("offers generation on the names alone, with the rest of Step 1 unfinished", () => {
    // The regression this pins: the button used to wait for the whole step, and Step 1 could not
    // be completed at all until UC-037/UC-041 moved land_id and the real-estate paper to Step 4.
    renderPanel();

    expect(screen.getByRole("button", { name: /generate document/i })).toBeEnabled();
  });

  it("shows nothing to preview until a letter has been generated", () => {
    // The letter is no longer filed on the case (UC-075), so an untouched case has no output at
    // all — not an old document waiting to be found.
    renderPanel();

    expect(screen.queryByTestId("preview")).not.toBeInTheDocument();
  });

  it("previews the finished job's own file, not a document on the case", async () => {
    job = { id: 7, status: "done", error: "" };
    renderPanel();

    await userEvent.click(screen.getByRole("button", { name: /generate document/i }));

    await waitFor(() => expect(screen.getByTestId("preview")).toHaveTextContent("job:7"));
    expect(screen.getByRole("button", { name: /regenerate/i })).toBeInTheDocument();
  });

  it("shows no generate button to someone who cannot edit the case", () => {
    renderPanel({ canGenerate: false });

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
