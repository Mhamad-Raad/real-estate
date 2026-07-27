"""RTL plumbing for authored `.docx` letter templates (§6.6).

Word stores direction as explicit flags, and getting them wrong fails *silently* — the file still
opens, it just renders left-to-right. Each helper here encodes one rule the probe established:

* `w:bidi` on the paragraph, `w:rtl` on the run — otherwise Sorani lays out LTR.
* the **complex-script** font slot (`w:cs`), not just `w:ascii`, is the one Arabic script reads.
* `w:bidiVisual` on the table, or column 1 renders on the left.
* no explicit `w:jc`: in a bidi paragraph the default *start* is the right margin, while
  `w:jc="right"` means *end* and pushes the text to the left.

Used by the template-authoring command and its test — not by the request path.
"""

from docx.oxml.ns import qn
from docx.shared import Pt

# Bundled with the worker image (fonts-noto-core); covers the Kurdish letters ڕ ێ ۆ ڵ ڤ.
RTL_FONT = "Noto Naskh Arabic"


def _insert_ordered(parent, tag: str, before_tags: list[str]):
    """Insert a child in schema order — OOXML silently ignores out-of-order elements."""
    element = parent.makeelement(qn(tag), {})
    successors = {qn(t) for t in before_tags}
    anchor = next((child for child in parent if child.tag in successors), None)
    if anchor is None:
        parent.append(element)
    else:
        anchor.addprevious(element)
    return element


def rtl_run(run, font: str = RTL_FONT, size_pt: float | None = None):
    """Mark a run right-to-left and point its complex-script font at a Sorani-capable face."""
    if size_pt is not None:
        run.font.size = Pt(size_pt)
    rPr = run._r.get_or_add_rPr()
    rFonts = rPr.get_or_add_rFonts()
    for slot in ("w:ascii", "w:hAnsi", "w:cs"):
        rFonts.set(qn(slot), font)
    rPr.append(rPr.makeelement(qn("w:rtl"), {}))
    return run


def rtl_paragraph(paragraph, text: str = "", font: str = RTL_FONT, size_pt: float | None = None):
    """Make a paragraph right-to-left and optionally add its text as one RTL run."""
    pPr = paragraph._p.get_or_add_pPr()
    _insert_ordered(pPr, "w:bidi", ["w:jc", "w:textDirection", "w:rPr", "w:sectPr"])
    if text:
        rtl_run(paragraph.add_run(text), font=font, size_pt=size_pt)
    return paragraph


def rtl_table(table):
    """Mirror the column order so column 1 sits on the right, as the paper form has it."""
    tblPr = table._tbl.tblPr
    _insert_ordered(
        tblPr, "w:bidiVisual", ["w:tblStyleRowBandSize", "w:tblW", "w:jc", "w:tblLook"]
    )
    return table
