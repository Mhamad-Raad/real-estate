import { render, screen } from "@testing-library/react";
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
