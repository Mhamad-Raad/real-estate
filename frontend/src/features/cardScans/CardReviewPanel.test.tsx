import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CardReviewPanel } from "./CardReviewPanel";
import type { CardScan } from "./types";

const unwrap = vi.fn().mockResolvedValue({ id: 1, document: 5 });
const confirmMutation = vi.fn(() => ({ unwrap }));

vi.mock("@/app/hooks", () => ({ useAppDispatch: () => vi.fn(), useAppSelector: () => "token" }));
vi.mock("@/lib/toast", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));
vi.mock("./cardScansApi", () => ({
  useConfirmCardScanMutation: () => [confirmMutation, { isLoading: false }],
}));

// The preview pane fetches the staged PDF with an auth header; irrelevant to these assertions.
beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, blob: async () => new Blob(["%PDF-"]) }),
  );
  vi.stubGlobal("URL", { ...URL, createObjectURL: () => "blob:x", revokeObjectURL: () => {} });
  confirmMutation.mockClear();
  unwrap.mockClear();
});

const field = (value: string, over = {}) => ({
  value,
  confidence: 90,
  source: "front" as const,
  verified: false,
  ...over,
});

const scan = (over: Partial<CardScan> = {}): CardScan => ({
  id: 7,
  document_type: "ClientID",
  status: "done",
  draft: {
    fields: {
      full_name: field("محمد رعد"),
      pid: field("200103487811", { source: "mrz+front", verified: true, confidence: 96 }),
      mother_full_name: field("دلسوز على", { confidence: 52 }),
      date_of_birth: field("2001-08-12", { source: "mrz", verified: true, confidence: 95 }),
    },
    warnings: [],
  },
  error: "",
  document: null,
  client: null,
  client_version: null,
  process: null,
  confirmed_at: null,
  confirmed_by: null,
  created_at: "2026-07-29T10:00:00Z",
  ...over,
});

const renderPanel = (over: Partial<CardScan> = {}) =>
  render(
    <CardReviewPanel
      scan={scan(over)}
      onConfirmed={vi.fn()}
      buildPayload={() => ({ assigned_lawyer: 3 })}
    />,
  );

describe("CardReviewPanel", () => {
  it("pre-fills every field from the reading", () => {
    renderPanel();
    expect(screen.getByLabelText(/Full name/)).toHaveValue("محمد رعد");
    expect(screen.getByLabelText(/Card number/)).toHaveValue("200103487811");
    expect(screen.getByLabelText(/Mother/)).toHaveValue("دلسوز على");
    expect(screen.getByLabelText(/Date of birth/)).toHaveValue("2001-08-12");
  });

  it("will not confirm until the match warning is acknowledged (§6.4)", async () => {
    const user = userEvent.setup();
    renderPanel();

    const submit = screen.getByRole("button", { name: /Confirm and create/ });
    expect(submit).toBeDisabled();

    await user.click(screen.getByRole("checkbox"));
    expect(submit).toBeEnabled();
    await user.click(submit);
    expect(confirmMutation).toHaveBeenCalledTimes(1);
  });

  it("sends the human's correction, not what the engine proposed", async () => {
    const user = userEvent.setup();
    renderPanel();

    const name = screen.getByLabelText(/Full name/);
    await user.clear(name);
    await user.type(name, "Corrected Name");
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: /Confirm and create/ }));

    expect(confirmMutation).toHaveBeenCalledWith(
      expect.objectContaining({ id: 7, full_name: "Corrected Name" }),
    );
  });

  it("keeps a failed reading usable — the fields are typed in by hand", async () => {
    const user = userEvent.setup();
    renderPanel({ status: "failed", draft: { fields: {}, warnings: [] } });

    expect(screen.getByText(/could not be read/)).toBeInTheDocument();
    const submit = screen.getByRole("button", { name: /Confirm and create/ });

    await user.type(screen.getByLabelText(/Full name/), "Typed By Hand");
    await user.type(screen.getByLabelText(/Card number/), "200103487811");
    await user.type(screen.getByLabelText(/Mother/), "Mother Name");
    await user.type(screen.getByLabelText(/Date of birth/), "2001-08-12");
    await user.click(screen.getByRole("checkbox"));

    expect(submit).toBeEnabled();
    await user.click(submit);
    expect(confirmMutation).toHaveBeenCalledWith(
      expect.objectContaining({ full_name: "Typed By Hand" }),
    );
  });

  it("cannot be confirmed with a field left empty", async () => {
    const user = userEvent.setup();
    renderPanel({
      draft: { fields: { full_name: field("Only A Name") }, warnings: [] },
    });

    await user.click(screen.getByRole("checkbox"));
    expect(screen.getByRole("button", { name: /Confirm and create/ })).toBeDisabled();
  });

  it("does not call an empty field an uncertain reading", () => {
    // A blank or failed read still returns every field at confidence 0; warning on those would
    // put a caution under every empty box while the lawyer types the card in by hand.
    renderPanel({
      status: "failed",
      draft: {
        fields: {
          pid: { value: "", confidence: 0, source: "", verified: false },
          full_name: { value: "", confidence: 0, source: "", verified: false },
        },
        warnings: [],
      },
    });
    expect(screen.queryByText(/reading was uncertain/)).not.toBeInTheDocument();
    expect(screen.queryByText(/From OCR/)).not.toBeInTheDocument();
  });

  it("shows the reading's warnings so they cannot be missed", () => {
    renderPanel({
      draft: { fields: {}, warnings: ["The machine-readable zone could not be read."] },
    });
    expect(screen.getByText(/machine-readable zone/)).toBeInTheDocument();
  });

  it("marks a cross-checked field differently from an uncertain one", () => {
    renderPanel();
    // The PID and the birth date both verified — one from the MRZ check digit, one from the
    // front and MRZ agreeing.
    expect(screen.getAllByText("Cross-checked")).toHaveLength(2);
    // The mother's name came back at 52%, so the lawyer is told to look at it.
    expect(screen.getByText(/reading was uncertain/)).toBeInTheDocument();
  });
});
