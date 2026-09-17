import { act, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CardPairCapture } from "./CardPairCapture";
import { cardBox } from "./frameAnalysis";
import type { CardSide } from "./cardSide";

// The camera and the pixel loop are mocked: this tests the two-step flow around them.
const camera = {
  active: false,
  videoRef: { current: null as HTMLVideoElement | null },
  open: vi.fn(async () => true),
  stop: vi.fn(),
  capture: vi.fn(async (name: string) => new File([new Uint8Array([1])], name, { type: "image/jpeg" })),
};
vi.mock("@/hooks/useCamera", () => ({ useCamera: () => camera }));

let onAutoCapture: ((region: { x: number; y: number; w: number; h: number }) => void) | null = null;
const auto = { phase: "searching", reset: vi.fn(), lock: vi.fn() };
vi.mock("./useAutoCapture", () => ({
  useAutoCapture: (args: { onCapture: typeof onAutoCapture }) => {
    onAutoCapture = args.onCapture;
    return auto;
  },
}));
vi.mock("@/lib/beep", () => ({ beep: vi.fn() }));
vi.mock("@/lib/toast", () => ({ toast: { error: vi.fn() } }));

const REGION = { x: 0.1, y: 0.2, w: 0.8, h: 0.6 };

function Harness({ back: initialBack = null }: { back?: CardSide | null }) {
  return <Stateful initialBack={initialBack} />;
}

function Stateful({ initialBack }: { initialBack: CardSide | null }) {
  const [front, setFront] = useState<CardSide | null>(null);
  const [back, setBack] = useState<CardSide | null>(initialBack);
  return (
    <>
      <CardPairCapture
        frontLabel="Front of the card"
        backLabel="Back of the card"
        front={front}
        back={back}
        onFront={setFront}
        onBack={setBack}
      />
      <span data-testid="front">{front?.file.name ?? ""}</span>
      <span data-testid="back">{back?.file.name ?? ""}</span>
    </>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  camera.active = false;
  onAutoCapture = null;
  vi.stubGlobal("URL", { ...URL, createObjectURL: vi.fn(() => "blob:x"), revokeObjectURL: vi.fn() });
});

describe("CardPairCapture", () => {
  it("opens the camera from either side and shows the guide for that side", async () => {
    render(<Harness />);
    await act(async () => {
      fireEvent.click(screen.getAllByRole("button", { name: "Use camera" })[1]);
    });
    expect(camera.open).toHaveBeenCalledTimes(1);

    // The mock's `active` is not state, so the switch to the other side is what re-renders.
    camera.active = true;
    await act(async () => {
      fireEvent.click(screen.getAllByRole("button", { name: "Use camera" })[0]);
    });
    expect(camera.open).toHaveBeenCalledTimes(1); // already open — only the target changed
    expect(screen.getByRole("status")).toHaveTextContent("Hold the card inside the frame");
  });

  it("takes the front, then asks for the back, then closes the camera", async () => {
    render(<Harness />);
    camera.active = true;
    await act(async () => {
      fireEvent.click(screen.getAllByRole("button", { name: "Use camera" })[0]);
    });

    await act(async () => onAutoCapture?.(REGION));
    expect(camera.capture).toHaveBeenCalledWith("front.jpg", REGION);
    expect(screen.getByTestId("front")).toHaveTextContent("front.jpg");
    expect(camera.stop).not.toHaveBeenCalled();
    expect(screen.getByRole("status")).toHaveTextContent("Front of the card taken.");

    await act(async () => onAutoCapture?.(REGION));
    expect(camera.capture).toHaveBeenLastCalledWith("back.jpg", REGION);
    expect(screen.getByTestId("back")).toHaveTextContent("back.jpg");
    expect(camera.stop).toHaveBeenCalledTimes(1);
  });

  it("closes after the front alone when the back is already attached", async () => {
    const back: CardSide = { file: new File([], "scan.pdf", { type: "application/pdf" }), url: "blob:b" };
    render(<Harness back={back} />);
    camera.active = true;
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Use camera" }));
    });

    await act(async () => onAutoCapture?.(REGION));
    expect(screen.getByTestId("front")).toHaveTextContent("front.jpg");
    expect(screen.getByTestId("back")).toHaveTextContent("scan.pdf");
    expect(camera.stop).toHaveBeenCalledTimes(1);
  });

  it("the shutter locks the loop so the side just taken is not taken again", async () => {
    render(<Harness />);
    camera.active = true;
    await act(async () => {
      fireEvent.click(screen.getAllByRole("button", { name: "Use camera" })[0]);
    });
    // A live frame with dimensions, so the shutter has something to crop.
    camera.videoRef.current = { videoWidth: 1920, videoHeight: 1080 } as HTMLVideoElement;

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Take the photo" }));
    });
    expect(auto.lock).toHaveBeenCalledTimes(1);
    expect(camera.capture).toHaveBeenCalledWith("front.jpg", cardBox(1920, 1080));
  });

  it("says so and stays closed when the camera is refused", async () => {
    camera.open.mockResolvedValueOnce(false);
    render(<Harness />);
    await act(async () => {
      fireEvent.click(screen.getAllByRole("button", { name: "Use camera" })[0]);
    });
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
