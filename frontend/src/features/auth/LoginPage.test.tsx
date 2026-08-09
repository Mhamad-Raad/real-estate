import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { buildStamp } from "@/lib/build";
import { LoginPage } from "./LoginPage";

vi.mock("@/app/hooks", () => ({
  useAppSelector: () => false,
  useAppDispatch: () => vi.fn(),
}));
vi.mock("react-router-dom", () => ({
  useNavigate: () => vi.fn(),
  Navigate: () => null,
}));
vi.mock("./authApi", () => ({ useLoginMutation: () => [vi.fn(), { isLoading: false }] }));
vi.mock("@/components/layout/LanguageSwitcher", () => ({ LanguageSwitcher: () => null }));
vi.mock("@/components/layout/ThemeToggle", () => ({ ThemeToggle: () => null }));

describe("LoginPage", () => {
  it("shows the build before anyone signs in", () => {
    // The placement matters as much as the component: this is the screen the office is looking
    // at when they phone about not being able to get in, so a refactor must not drop it.
    render(<LoginPage />);
    expect(screen.getByText(buildStamp)).toBeInTheDocument();
  });
});
