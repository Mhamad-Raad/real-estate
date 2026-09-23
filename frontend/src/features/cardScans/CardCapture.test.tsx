import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CardCapture } from "./CardCapture";
import type { CardSide } from "./cardSide";

const side = (name: string, type: string): CardSide => ({
  file: new File([new Uint8Array([1, 2, 3])], name, { type }),
  url: `blob:${name}`,
});

const renderSide = (s: CardSide | null) =>
  render(<CardCapture label="Front of the card" side={s} onChange={vi.fn()} />);

// The office scans cards on a device that delivers TIFF, and no browser can draw one (UC-087).
describe("CardCapture preview", () => {
  it("shows a picked JPEG as an image", () => {
    renderSide(side("card.jpg", "image/jpeg"));

    expect(screen.getByAltText("Front of the card")).toBeInTheDocument();
  });

  it("names the file instead of leaving a broken image the browser cannot draw", () => {
    renderSide(side("scan001.tiff", "image/tiff"));

    // The tag is what discovers this — a TIFF has a perfectly ordinary image MIME type.
    fireEvent.error(screen.getByAltText("Front of the card"));

    expect(screen.getByText("scan001.tiff")).toBeInTheDocument();
    expect(screen.queryByAltText("Front of the card")).not.toBeInTheDocument();
  });

  it("goes back to a real preview once a readable side replaces the unreadable one", () => {
    const { rerender } = renderSide(side("scan001.tiff", "image/tiff"));
    fireEvent.error(screen.getByAltText("Front of the card"));

    rerender(
      <CardCapture label="Front of the card" side={side("retake.png", "image/png")} onChange={vi.fn()} />,
    );

    expect(screen.getByAltText("Front of the card")).toBeInTheDocument();
  });

  it("offers the camera only when a session is there to hand it to", () => {
    const { rerender } = renderSide(null);
    expect(screen.queryByRole("button", { name: "Use camera" })).not.toBeInTheDocument();

    const onUseCamera = vi.fn();
    rerender(<CardCapture label="Front of the card" side={null} onChange={vi.fn()} onUseCamera={onUseCamera} />);
    fireEvent.click(screen.getByRole("button", { name: "Use camera" }));
    expect(onUseCamera).toHaveBeenCalledTimes(1);
  });

  it("offers only the formats the server can read", () => {
    // `image/*` also offered WebP, GIF and HEIC, which preview fine and are refused on Read.
    const { container } = renderSide(null);

    const accept = container.querySelector("input[type=file]")?.getAttribute("accept");
    expect(accept).toBe("application/pdf,image/jpeg,image/png,image/tiff");
  });
});
