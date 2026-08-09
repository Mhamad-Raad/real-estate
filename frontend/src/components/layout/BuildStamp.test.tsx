import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BuildStamp, buildStamp } from "./BuildStamp";

describe("BuildStamp", () => {
  it("shows the version baked in at build time", () => {
    render(<BuildStamp />);
    expect(screen.getByText(buildStamp)).toBeInTheDocument();
  });

  it("keeps Latin digits and LTR so it matches git and a typed bug report", () => {
    render(<BuildStamp />);
    const el = screen.getByText(buildStamp);
    expect(el).toHaveAttribute("dir", "ltr");
    // The §9 digit sweep must never convert this to ١.٠.٠ — pinned here so it fails loudly.
    expect(el.textContent).toMatch(/^\d+\.\d+\.\d+ \(build \d+\)$/);
  });
});
