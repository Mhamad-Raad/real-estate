import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ClientFields } from "./ClientFields";
import type { ClientInput } from "./types";
import { EMPTY_CLIENT } from "./clientForm";

vi.mock("@/features/categories/categoriesApi", () => ({
  useListCategoriesQuery: () => ({ data: [] }),
}));

const married = { ...EMPTY_CLIENT, marital_status: "married" as const };

const renderFields = (value: ClientInput = married) =>
  render(<ClientFields value={value} onChange={vi.fn()} showCategory={false} />);

/** The order the inputs actually appear in the document. */
const order = (...ids: string[]) => {
  const nodes = ids.map((suffix) => {
    const node = document.getElementById(`c-${suffix}`);
    if (!node) throw new Error(`no input #c-${suffix}`);
    return node;
  });
  return nodes.every(
    (node, i) =>
      i === 0 ||
      // eslint-disable-next-line no-bitwise
      (nodes[i - 1].compareDocumentPosition(node) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0,
  );
};

// The form asked about the spouse in the middle of asking about the beneficiary (UC-089).
describe("ClientFields layout", () => {
  it("asks for everything about the beneficiary before the spouse", () => {
    renderFields();

    expect(order("dob", "pob", "phone", "address", "spouse")).toBe(true);
  });

  it("keeps the spouse block together at the end", () => {
    renderFields();

    expect(order("address", "spouse", "spouse-dob", "spouse-mother", "spouse-pid")).toBe(true);
  });

  it("gives the address the same width as every other field", () => {
    // It spanned the row, so the address was twice the width of the phone beside it.
    renderFields();

    expect(screen.getByLabelText(/address/i).closest("div")).not.toHaveClass("sm:col-span-2");
  });

  it("shows no spouse fields for an unmarried beneficiary", () => {
    renderFields(EMPTY_CLIENT);

    expect(document.getElementById("c-spouse")).toBeNull();
  });
});


// `pid.test.ts` proves the filter works; these prove the boxes actually call it. A helper wired to
// the wrong field would leave that unit test just as green — which is how the spouse box shipped
// unfiltered while the beneficiary's own was done (reported by the office, 2026-08-20).
//
// One keystroke per assertion, deliberately: the input is **controlled** by the `value` prop, and
// the parent here is a mock that never feeds a new one back — so the box is empty before every
// keystroke and only the filtering of that single character can be observed. Accumulation and the
// 12-digit cap are `pid.test.ts`'s job.
describe("national ID boxes filter as they are typed", () => {
  const typeOne = async (id: string, char: string) => {
    // Testing Library cleans up between *tests*, not between renders inside one — without this the
    // second lookup finds the first render's node, whose `onChange` is a different mock.
    cleanup();
    const onChange = vi.fn();
    render(<ClientFields value={married} onChange={onChange} showCategory={false} />);
    await userEvent.type(document.getElementById(id) as HTMLInputElement, char);
    return onChange.mock.calls.at(-1)?.[0] as ClientInput;
  };

  it("drops a letter from the beneficiary's ID", async () => {
    expect((await typeOne("c-pid", "a")).pid).toBe("");
    expect((await typeOne("c-pid", "7")).pid).toBe("7");
  });

  it("drops a letter from the SPOUSE's ID", async () => {
    expect((await typeOne("c-spouse-pid", "a")).spouse_pid).toBe("");
    expect((await typeOne("c-spouse-pid", "7")).spouse_pid).toBe("7");
  });

  it("folds an Arabic-Indic digit in both boxes", async () => {
    expect((await typeOne("c-pid", "٧")).pid).toBe("7");
    expect((await typeOne("c-spouse-pid", "٧")).spouse_pid).toBe("7");
  });
});
