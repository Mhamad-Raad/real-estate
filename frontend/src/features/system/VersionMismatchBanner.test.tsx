import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { VersionMismatchBanner } from "./VersionMismatchBanner";

let health: { status: string; app_version: string; build: number } | undefined;

vi.mock("./systemApi", () => ({ useGetHealthQuery: () => ({ data: health }) }));

beforeEach(() => {
  health = undefined;
});

describe("VersionMismatchBanner", () => {
  it("stays silent while health has not answered", () => {
    render(<VersionMismatchBanner />);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("stays silent when the server is on the same build", () => {
    health = { status: "ok", app_version: __APP_VERSION__, build: __APP_BUILD__ };
    render(<VersionMismatchBanner />);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("warns, and names both builds, when they disagree", () => {
    health = { status: "ok", app_version: "9.9.9", build: __APP_BUILD__ + 1 };
    render(<VersionMismatchBanner />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText(/server 9\.9\.9 \(build \d+\)/)).toBeInTheDocument();
  });

  it("stays silent when the server build is unknown, rather than crying wolf", () => {
    // Build 0 is the "could not resolve" marker — a dev run or a build made without VERSION.
    health = { status: "ok", app_version: "0.0.0", build: 0 };
    render(<VersionMismatchBanner />);
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
