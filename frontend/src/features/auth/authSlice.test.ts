import { describe, expect, it } from "vitest";

import reducer, { setAccess } from "./authSlice";

// The refresh token ROTATES (`ROTATE_REFRESH_TOKENS`) and the spent one is blacklisted
// (`BLACKLIST_AFTER_ROTATION`). Keeping only the access token worked exactly once: the next
// silent refresh sent the blacklisted token, was refused, and signed the user out mid-work about
// an hour into their day (UC-071).
describe("setAccess during a silent refresh", () => {
  const signedIn = { access: "old-access", refresh: "old-refresh", user: null };

  it("stores the rotated refresh token alongside the new access token", () => {
    const next = reducer(signedIn, setAccess({ access: "new-access", refresh: "new-refresh" }));

    expect(next.access).toBe("new-access");
    expect(next.refresh).toBe("new-refresh");
    expect(localStorage.getItem("refresh_token")).toBe("new-refresh");
  });

  it("keeps the existing refresh token when the server rotates nothing", () => {
    const next = reducer(signedIn, setAccess({ access: "new-access" }));

    expect(next.access).toBe("new-access");
    expect(next.refresh).toBe("old-refresh");
  });
});
