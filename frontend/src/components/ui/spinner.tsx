import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

// Direction-agnostic loading spinner (rotation is unaffected by RTL).
export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("size-4 animate-spin", className)} aria-hidden />;
}
