import type { ThemeMode } from "@/features/ui/uiSlice";
import { cn } from "@/lib/utils";

/**
 * A miniature of the app — sidebar, header, cards — drawn entirely from the design tokens, so it
 * carries no colours of its own and renders whatever theme its wrapper scopes.
 * Direction follows the page, so it mirrors in RTL exactly as the real screen does.
 */
function ScreenPreview({ className }: { className?: string }) {
  return (
    <div className={cn("flex h-24 bg-background", className)}>
      <div className="flex w-10 shrink-0 flex-col gap-1.5 border-e bg-sidebar p-1.5">
        <div className="h-3 rounded-sm bg-primary/80" />
        <div className="h-2 rounded-sm bg-muted" />
        <div className="h-2 rounded-sm bg-muted" />
        <div className="h-2 rounded-sm bg-muted" />
      </div>
      <div className="flex-1 space-y-2 p-2">
        <div className="flex items-center justify-between gap-2">
          <div className="h-2 w-14 rounded-sm bg-foreground/70" />
          <div className="size-3 shrink-0 rounded-full bg-accent" />
        </div>
        <div className="grid grid-cols-3 gap-1.5">
          {[0, 1, 2].map((i) => (
            <div key={i} className="space-y-1 rounded-sm border bg-card p-1.5">
              <div className="h-1.5 w-2/3 rounded-xs bg-muted" />
              <div
                className={cn(
                  "h-2.5 w-1/2 rounded-xs",
                  i === 0 ? "bg-primary" : "bg-muted-foreground/40",
                )}
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/**
 * The app as it would look in `mode` — used by the mode cards, and by the palette cards, which
 * pass the *resolved* theme so a card never advertises a screen the user is not looking at.
 * The `preview-*` classes re-declare the design tokens on this subtree; every Tailwind colour
 * utility is `@theme inline`, i.e. it reads the token at the element, so the miniature inside
 * picks them up without knowing anything about themes.
 */
export function ThemePreview({ mode }: { mode: ThemeMode }) {
  // "System" is the one choice that cannot honestly be shown as a single screen.
  if (mode === "system") {
    return (
      <div className="grid grid-cols-2">
        <div className="preview-light overflow-hidden">
          <ScreenPreview />
        </div>
        <div className="preview-dark overflow-hidden">
          <ScreenPreview />
        </div>
      </div>
    );
  }

  return (
    <div className={mode === "dark" ? "preview-dark" : "preview-light"}>
      <ScreenPreview />
    </div>
  );
}
