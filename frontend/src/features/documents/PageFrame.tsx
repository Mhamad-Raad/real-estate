import { cn } from "@/lib/utils";

/**
 * An inline PDF frame sized to the page, not to a number (UC-123). The viewer fits the page to the
 * frame's width, so a fixed height showed half a page; the ratio is the page's own 1:1.41 plus
 * room for the viewer's toolbar, and the cap keeps a wide screen from getting a frame taller than
 * the window it is scrolled in.
 */
export function PageFrame({ className, ...props }: React.ComponentProps<"iframe">) {
  return (
    <iframe
      {...props}
      className={cn("aspect-[2/3] h-auto max-h-[75vh] w-full rounded-md border border-border bg-white", className)}
    />
  );
}
