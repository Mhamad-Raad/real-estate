import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
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


/** One keystroke into one box, and the draft the field handed back.
 *
 * One keystroke per assertion, deliberately: the input is **controlled** by the `value` prop, and
 * the parent here is a mock that never feeds a new one back — so the box is empty before every
 * keystroke and only the filtering of that single character can be observed. Accumulation and the
 * 12-digit cap are `pid.test.ts`'s job.
 */
const typeOne = async (id: string, char: string) => {
  // Testing Library cleans up between *tests*, not between renders inside one — without this the
  // second lookup finds the first render's node, whose `onChange` is a different mock.
  cleanup();
  const onChange = vi.fn();
  render(<ClientFields value={married} onChange={onChange} showCategory={false} />);
  await userEvent.type(document.getElementById(id) as HTMLInputElement, char);
  return onChange.mock.calls.at(-1)?.[0] as ClientInput;
};

// `pid.test.ts` proves the filter works; these prove the boxes actually call it. A helper wired to
// the wrong field would leave that unit test just as green — which is how the spouse box shipped
// unfiltered while the beneficiary's own was done (reported by the office, 2026-08-20).
describe("national ID boxes filter as they are typed", () => {
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

// Same lesson as the ID boxes, and the same trap: a name box wired to the plain setter would look
// identical on screen and let a digit onto the printed letter (the office, 2026-09-22).
describe("name boxes refuse a digit as it is typed", () => {
  it("drops a digit from the beneficiary's own name and their mother's", async () => {
    expect((await typeOne("c-name", "2")).full_name).toBe("");
    expect((await typeOne("c-name", "K")).full_name).toBe("K");
    expect((await typeOne("c-mother", "2")).mother_full_name).toBe("");
  });

  it("drops a digit from BOTH spouse names", async () => {
    expect((await typeOne("c-spouse", "2")).spouse_name).toBe("");
    expect((await typeOne("c-spouse-mother", "2")).spouse_mother_full_name).toBe("");
  });

  it("drops an Arabic-Indic digit, which is just as much a number", async () => {
    expect((await typeOne("c-name", "٧")).full_name).toBe("");
    expect((await typeOne("c-name", "۹")).full_name).toBe("");
  });
});

// The mock parent above never feeds a new `value` back, so the caret can only be observed with a
// real one: a refused keystroke is exactly the case where React restores what it rendered.
describe("a refused digit does not move the cursor", () => {
  function Stateful() {
    const [value, setValue] = useState<ClientInput>(EMPTY_CLIENT);
    return <ClientFields value={value} onChange={setValue} showCategory={false} />;
  }

  it("leaves the caret mid-name, where the lawyer was typing", async () => {
    cleanup();
    render(<Stateful />);
    const box = document.getElementById("c-name") as HTMLInputElement;
    await userEvent.type(box, "Karwan Ahmed");

    await userEvent.type(box, "5", { initialSelectionStart: 6, initialSelectionEnd: 6 });

    expect(box).toHaveValue("Karwan Ahmed");
    expect(box.selectionStart).toBe(6);
  });

  it("still inserts an accepted letter where the caret is", async () => {
    cleanup();
    render(<Stateful />);
    const box = document.getElementById("c-name") as HTMLInputElement;
    await userEvent.type(box, "Karwan Ahmed");

    await userEvent.type(box, "i", { initialSelectionStart: 6, initialSelectionEnd: 6 });

    expect(box).toHaveValue("Karwani Ahmed");
    expect(box.selectionStart).toBe(7);
  });
});
