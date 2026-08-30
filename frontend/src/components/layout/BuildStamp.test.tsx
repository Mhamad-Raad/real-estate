import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { buildStamp, formatBuild } from "@/lib/build";
import { BuildStamp } from "./BuildStamp";

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

  it("formats this bundle and the server identically", () => {
    // The mismatch banner prints both side by side; one formatter is what keeps them comparable.
    expect(formatBuild("1.2.3", 9)).toBe("1.2.3 (build 9)");
    expect(buildStamp).toBe(formatBuild(__APP_VERSION__, __APP_BUILD__));
  });
});
