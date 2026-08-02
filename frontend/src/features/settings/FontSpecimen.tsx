import type { FontChoice } from "@/features/ui/uiSlice";

// The specimen carries the Sorani letters that rule most Arabic faces out, so a face that somehow
// slipped past the glyph audit shows itself here rather than in a filed letter.
const SORANI_SPECIMEN = "ئەم نووسینە ڕەنگە پۆلێ گەورە بێت";
const LATIN_SPECIMEN = "Aa Bb Cc — 0123456789 ٠١٢٣٤٥٦٧٨٩";

/**
 * How one typeface actually renders. `data-font` sets both family variables on this subtree, so
 * the sample is drawn in the face itself — Sorani above, Latin and digits below, because the
 * choice governs both scripts (UC-031). Each line is direction-isolated: an RTL specimen inside
 * an LTR page (or the reverse) otherwise drags neighbouring punctuation across.
 */
export function FontSpecimen({ font }: { font: FontChoice }) {
  return (
    <div data-font={font} className="space-y-1 bg-muted/30 px-3 py-4 text-center">
      <p
        lang="ckb"
        dir="rtl"
        className="truncate text-lg leading-tight"
        style={{ fontFamily: "var(--font-arabic)" }}
      >
        {SORANI_SPECIMEN}
      </p>
      <p
        dir="ltr"
        className="truncate text-xs text-muted-foreground"
        style={{ fontFamily: "var(--font-sans)" }}
      >
        {LATIN_SPECIMEN}
      </p>
    </div>
  );
}
