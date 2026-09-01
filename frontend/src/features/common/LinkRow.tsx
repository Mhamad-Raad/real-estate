import type { KeyboardEvent, MouseEvent, ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";

/**
 * A table row that is itself the way into its detail page (UC-119).
 *
 * The office had to find the one clickable word or button in a row, and it differed by page.
 * Now the whole row goes there, on click and on Enter, without taking anything away: the
 * controls inside it — a checkbox, a delete button, a link that opens in a new tab — keep their
 * own meaning, and a drag to select text is not a click.
 */
export function LinkRow({
  to,
  label,
  className,
  children,
}: {
  to: string;
  /** Read by assistive tech for the row as a whole, since its cells are plain text. */
  label: string;
  className?: string;
  children: ReactNode;
}) {
  const navigate = useNavigate();

  const onClick = (e: MouseEvent<HTMLTableRowElement>) => {
    // Anything interactive inside the row handles its own click.
    if ((e.target as HTMLElement).closest("a,button,input,label,[role='button'],[role='menuitem']")) return;
    if (window.getSelection()?.toString()) return;
    navigate(to);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTableRowElement>) => {
    // Only when the row itself has focus — Enter on a control inside it belongs to that control.
    if (e.key !== "Enter" || e.target !== e.currentTarget) return;
    e.preventDefault();
    navigate(to);
  };

  return (
    <TableRow
      role="link"
      tabIndex={0}
      aria-label={label}
      className={cn("cursor-pointer focus-visible:bg-muted focus-visible:outline-none", className)}
      onClick={onClick}
      onKeyDown={onKeyDown}
    >
      {children}
    </TableRow>
  );
}
