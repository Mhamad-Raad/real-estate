import { describe, expect, it } from "vitest";

import { PROCESS_LIST_TAG } from "@/features/processes/processesApi";

/**
 * The stale-cache trap this guards: RTK Query does NOT match a bare `"Process"` tag against an
 * invalidation of `{type:"Process", id:"LIST"}`, which is what every processesApi mutation
 * emits. A dashboard tagged `["Process"]` silently keeps showing pre-change numbers — invisible
 * in the UI until someone notices it disagrees with the processes list.
 *
 * The real protection is structural: dashboardApi and reportsApi import this one constant
 * instead of writing their own tag. This asserts the constant keeps the id-scoped shape, so
 * flattening it back to a general tag breaks the build here rather than in the office.
 */
describe("process-derived cache invalidation", () => {
  it("uses the id-scoped LIST tag that process mutations invalidate", () => {
    expect(PROCESS_LIST_TAG).toEqual({ type: "Process", id: "LIST" });
  });
});
