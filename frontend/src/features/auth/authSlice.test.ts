import { describe, expect, it } from "vitest";

import reducer, { logOut, setAccess, setCredentials } from "./authSlice";

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
    expect(sessionStorage.getItem("refresh_token")).toBe("new-refresh");
  });

  it("keeps the existing refresh token when the server rotates nothing", () => {
    const next = reducer(signedIn, setAccess({ access: "new-access" }));

    expect(next.access).toBe("new-access");
    expect(next.refresh).toBe("old-refresh");
  });
});

// These are shared office computers and a refresh token is good for a week (UC-071), so a token
// that outlives the browser signs the next person in as the last one (It.8).
describe("where the tokens are kept", () => {
  it("writes to sessionStorage and never to localStorage", () => {
    localStorage.clear();
    sessionStorage.clear();

    reducer(undefined, setCredentials({ access: "a", refresh: "r" }));

    expect(sessionStorage.getItem("access_token")).toBe("a");
    expect(sessionStorage.getItem("refresh_token")).toBe("r");
    expect(localStorage.getItem("access_token")).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
  });

  it("clears both halves on sign-out", () => {
    reducer(undefined, setCredentials({ access: "a", refresh: "r" }));
    reducer(undefined, logOut());

    expect(sessionStorage.getItem("access_token")).toBeNull();
    expect(sessionStorage.getItem("refresh_token")).toBeNull();
  });
});
