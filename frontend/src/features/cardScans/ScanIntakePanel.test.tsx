import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useEffect } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ScanIntakePanel } from "./ScanIntakePanel";
import type { CardScan } from "./types";

const field = (value: string) => ({ value, confidence: 60, source: "back", verified: false });

let reading: CardScan;

vi.mock("@/app/hooks", () => ({ useAppDispatch: () => vi.fn(), useAppSelector: () => "token" }));
vi.mock("@/lib/toast", () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("./cardScansApi", () => ({
  useStageCardScanMutation: () => [() => ({ unwrap: async () => ({ id: 7 }) }), { isLoading: false }],
  useConfirmCardScanMutation: () => [vi.fn(), { isLoading: false }],
}));
// The reading settles the moment a card is staged — polling is `useCardReading`'s own concern.
vi.mock("./useCardReading", () => ({
  useCardReading: (scanId: number | null, onDone: (scan: CardScan) => void) => {
    useEffect(() => {
      if (scanId !== null) onDone({ ...reading, id: scanId });
    }, [scanId]); // eslint-disable-line react-hooks/exhaustive-deps
    return { reading: false };
  },
}));
vi.mock("./CardPairCapture", () => ({
  CardPairCapture: ({ onFront }: { onFront: (side: unknown) => void }) => (
    <button type="button" onClick={() => onFront({ file: new File(["x"], "front.png") })}>
      take front
    </button>
  ),
}));

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, blob: async () => new Blob(["%PDF-"]) }));
  vi.stubGlobal("URL", { ...URL, createObjectURL: () => "blob:x", revokeObjectURL: () => {} });
  reading = {
    id: 0,
    document_type: "ClientID",
    status: "done",
    draft: { fields: { place_of_birth: field("كركوك") }, warnings: [] },
    error: "",
    document: null,
    client: null,
    client_version: null,
    process: null,
    confirmed_at: null,
    confirmed_by: null,
    created_at: "2026-09-28T00:00:00Z",
  } as CardScan;
});

const readACard = async () => {
  render(<ScanIntakePanel category={1} assignedLawyer={3} landId="" landAddress="" onCreated={vi.fn()} />);
  await userEvent.click(screen.getByRole("button", { name: "take front" }));
  await userEvent.click(screen.getByRole("button", { name: /Read the card/ }));
};

describe("ScanIntakePanel", () => {
  it("pre-fills the birthplace from the back of the card, marked for checking (UC-128)", async () => {
    await readACard();

    expect(await screen.findByLabelText("Place of birth")).toHaveValue("كركوك");
    expect(screen.getByText(/check it/i)).toBeInTheDocument();
  });

  it("leaves the birthplace empty when the back gave none", async () => {
    reading.draft.fields = {};
    await readACard();

    expect(await screen.findByLabelText("Place of birth")).toHaveValue("");
  });
});
