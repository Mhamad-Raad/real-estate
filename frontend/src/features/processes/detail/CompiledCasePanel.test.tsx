import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { DocumentMeta } from "@/features/documents/types";

import { CompiledCasePanel } from "./CompiledCasePanel";

const unwrap = vi.fn().mockResolvedValue({ id: 7 });
const compile = vi.fn((_args: { process: number }) => ({ unwrap }));
let job: { id: number; status: string; error: string } | undefined;

vi.mock("@/app/hooks", () => ({ useAppDispatch: () => vi.fn(), useAppSelector: () => "token" }));
vi.mock("@/lib/toast", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@/features/documents/DocumentRow", () => ({
  DocumentRow: ({ deletable }: { deletable?: boolean }) => (
    <div data-testid="row">{deletable === false ? "locked" : "deletable"}</div>
  ),
}));
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
    useCompileCaseMutation: () => [compile, { isLoading: false }],
    useGetGenerationJobQuery: (_id: number, opts?: { skip?: boolean }) => ({
      data: opts?.skip ? undefined : job,
    }),
  };
});

const doc = (over: Partial<DocumentMeta> = {}): DocumentMeta =>
  ({
    id: 1,
    document_type: "ClientID",
    display_filename: "f.pdf",
    input_source: "imported",
    ...over,
  }) as DocumentMeta;

const ATTACHED = [doc()];
// An export the app stored before UC-118 — still a document on the case until it is retired.
const STORED_EXPORT = doc({ id: 2, document_type: "CompiledCase", input_source: "system_generated" });
const WITH_EXPORT = [doc(), STORED_EXPORT];
// The paper case file itself, carried in through the backlog door (UC-114).
const SCANNED_CASE = doc({ id: 3, document_type: "CompiledCase", input_source: "imported" });

function renderPanel(props: Partial<Parameters<typeof CompiledCasePanel>[0]> = {}) {
  return render(
    <CompiledCasePanel
      processId={1}
      documents={ATTACHED}
      canEdit
      isAdmin={false}
      isComplete={false}
      autoStart={false}
      {...props}
    />,
  );
}

// Closing the case is what compiles it (UC-086) — the office was pressing two buttons to finish
// one, and a case closed without the second press had no export at all.
describe("CompiledCasePanel", () => {
  beforeEach(() => {
    job = undefined;
    compile.mockClear();
  });

  it("offers no compile button while the case is still open", () => {
    renderPanel();

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("compiles off the press that closed the case", async () => {
    job = { id: 7, status: "done", error: "" };

    renderPanel({ isComplete: true, autoStart: true });

    await waitFor(() => expect(compile).toHaveBeenCalledWith({ process: 1 }));
    expect(compile).toHaveBeenCalledTimes(1);
  });

  it("does not compile a case that was merely opened while already complete", () => {
    // The reason `autoStart` is a press and not the status: this would otherwise write a new
    // export to every old case each time somebody looked at one.
    renderPanel({ isComplete: true });

    expect(compile).not.toHaveBeenCalled();
  });

  it("replaces an export that predates the closing press", async () => {
    // An older case may already carry one, and it was compiled before the case was finished —
    // the file the office prints must be the one that matches the closed case.
    renderPanel({ documents: WITH_EXPORT, isComplete: true, autoStart: true });

    await waitFor(() => expect(compile).toHaveBeenCalledTimes(1));
  });

  it("keeps recompiling available on a case amended after it closed", () => {
    renderPanel({ documents: WITH_EXPORT, isComplete: true });

    expect(screen.getByRole("button", { name: /recompile/i })).toBeInTheDocument();
    expect(screen.getByTestId("preview")).toHaveTextContent("document:2");
  });

  it("shows the finished export from the job, not from the case (UC-118)", async () => {
    // Nothing is filed any more: the export is a one-read job file, previewed while it lasts.
    job = { id: 7, status: "done", error: "" };

    renderPanel({ documents: WITH_EXPORT, isComplete: true, autoStart: true });

    await waitFor(() => expect(screen.getByTestId("preview")).toHaveTextContent("job:7"));
    expect(screen.getAllByTestId("preview")).toHaveLength(1);
  });

  it("treats a scanned case file as something worth compiling", () => {
    // The backlog door files the paper case itself as a CompiledCase (UC-114): that scan *is*
    // the case's papers, so the export of such a case is the cover sheet plus the scan.
    renderPanel({ documents: [SCANNED_CASE], isComplete: true });

    expect(screen.getByRole("button", { name: /recompile/i })).toBeEnabled();
  });

  it("names the scanned case file as the only copy, and keeps its delete for admins", () => {
    renderPanel({ documents: [SCANNED_CASE], isComplete: true });

    expect(screen.getByText(/only copy/i)).toBeInTheDocument();
    expect(screen.getByTestId("row")).toHaveTextContent("locked");
  });

  it("lets an admin delete the scanned case file", () => {
    renderPanel({ documents: [SCANNED_CASE], isComplete: true, isAdmin: true });

    expect(screen.getByTestId("row")).toHaveTextContent("deletable");
  });

  it("says nothing special about a stored export", () => {
    renderPanel({ documents: WITH_EXPORT, isComplete: true });

    expect(screen.queryByText(/only copy/i)).not.toBeInTheDocument();
    expect(screen.getByTestId("row")).toHaveTextContent("deletable");
  });

  it("does not count a stored export as something to merge", () => {
    // It would only nest inside the next export — a case carrying nothing else has no papers.
    renderPanel({ documents: [STORED_EXPORT], isComplete: true });

    expect(screen.getByRole("button", { name: /recompile/i })).toBeDisabled();
  });

  it("leaves a complete case with no export a way to produce one", () => {
    // A compile that failed, or a case closed before this rule existed.
    renderPanel({ isComplete: true });

    expect(screen.getByRole("button", { name: /compile/i })).toBeEnabled();
  });

  it("does not compile itself later when the closing press had nothing to merge", async () => {
    // A case force-closed with no documents: the press is the trigger, and attaching the first
    // paper afterwards must not silently produce an export nobody asked for.
    const { rerender } = renderPanel({ documents: [], isComplete: true, autoStart: true });

    rerender(
      <CompiledCasePanel
        processId={1}
        documents={ATTACHED}
        canEdit
        isAdmin={false}
        isComplete
        autoStart
      />,
    );
    await Promise.resolve();

    expect(compile).not.toHaveBeenCalled();
  });

  it("shows no button at all to someone who cannot edit the case", () => {
    renderPanel({ documents: WITH_EXPORT, isComplete: true, canEdit: false });

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
