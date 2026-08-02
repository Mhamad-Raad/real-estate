import { cn } from "@/lib/utils";

export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  // `bg-muted` on a near-white surface was almost invisible even on a 3s stall (UC-006), which is
  // why the office reported "no loading states". A step darker in light mode, unchanged in dark.
  return (
    <div
      className={cn("animate-pulse rounded-md bg-black/10 dark:bg-white/10", className)}
      {...props}
    />
  );
}
