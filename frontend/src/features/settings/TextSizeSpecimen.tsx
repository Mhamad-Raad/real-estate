import type { TextSize } from "@/features/ui/uiSlice";

/**
 * A field drawn at the size the setting produces.
 *
 * The size is read out of the stylesheet — `[data-text="…"]` publishes each level as
 * `--text-scale` — rather than copied into a table here. A preview built from a second copy of
 * the scale stops telling the truth the moment one of the two is edited, and a settings card that
 * misrepresents its own option is worse than no preview.
 *
 * Everything inside is sized in `em`, not `rem`: `rem` always resolves against the document root,
 * so a preview built the way the rest of the app is built would render every card identically.
 */
export function TextSizeSpecimen({
  size,
  label,
  value,
}: {
  size: TextSize;
  label: string;
  value: string;
}) {
  return (
    // The same attribute the app sets on <html>: the preset applies its own font-size here, so
    // the card is drawn by the very rule the option switches on.
    <div data-text={size} className="bg-muted/30 px-3 py-4">
      <p className="text-muted-foreground" style={{ fontSize: "0.75em", marginBottom: "0.35em" }}>
        {label}
      </p>
      <p
        className="truncate rounded-md border border-input bg-background"
        style={{ fontSize: "0.875em", padding: "0.5em 0.75em" }}
      >
        {value}
      </p>
    </div>
  );
}
