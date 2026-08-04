import { describe, expect, it } from "vitest";

import { PROCESS_LIST_TAG } from "@/features/processes/processesApi";

import { confirmInvalidates } from "./cardScansApi";
import type { CardScan } from "./types";

// Filing a spouse card onto an open case (UC-048) has to refresh that case's detail. The detail
// query provides `{type:'Process', id}` and `PROCESS_LIST_TAG` is `id:'LIST'` — RTK Query does
// **not** match one against the other, so invalidating only LIST leaves Step 1 still reporting
// the spouse ID missing until a reload. This is the silent stale-cache class hit once in It.4.
describe("confirmCardScan invalidation", () => {
  it("invalidates the id-scoped process tag when the scan was filed onto a case", () => {
    const tags = confirmInvalidates({ process: 42 } as CardScan);
    expect(tags).toContainEqual({ type: "Process", id: 42 });
    expect(tags).toContainEqual(PROCESS_LIST_TAG);
    expect(tags).toContain("Client");
  });

  it("still refreshes the lists when there is no case to scope to", () => {
    const tags = confirmInvalidates({ process: null } as unknown as CardScan);
    expect(tags).toContainEqual(PROCESS_LIST_TAG);
    expect(tags).toContain("Client");
    expect(tags.some((t) => typeof t === "object" && t.id !== "LIST")).toBe(false);
  });
});
