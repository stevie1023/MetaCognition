#!/usr/bin/env python3
"""Render figures/figure1_taxonomy.svg into PNG and an editable PPTX.

  python3 render.py

Geometry comes from build.layout(), so the PNG and the PPTX are guaranteed to
match the SVG. The PPTX is built as native shapes (not a picture of the SVG),
so box positions, colours and text stay editable in PowerPoint.

cairosvg needs libcairo; we set DYLD_FALLBACK_LIBRARY_PATH so the bundled Python
can find Homebrew's copy without any system-wide install.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIG = ROOT / "figures"
SVG = FIG / "figure1_taxonomy.svg"
PNG = FIG / "figure1_taxonomy.png"
PPTX = FIG / "figure1_taxonomy.pptx"

if "/opt/homebrew/lib" not in os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", ""):
    os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = (
        "/opt/homebrew/lib:" + os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
    )

import re

import build as B

PX = 9525  # EMU per pixel at 96 dpi


def make_png():
    import cairosvg
    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', SVG.read_text(encoding="utf-8"))
    w, h = (float(m.group(1)), float(m.group(2))) if m else (2420.0, 2000.0)
    cairosvg.svg2png(
        url=str(SVG), write_to=str(PNG),
        output_width=int(w * 2), output_height=int(h * 2),
    )
    return PNG


def make_pptx():
    """Rebuild the taxonomy as native, editable PowerPoint shapes."""
    import yaml
    from pptx import Presentation
    from pptx.util import Emu, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

    tax = yaml.safe_load((ROOT / "notes" / "taxonomy.yaml").read_text(encoding="utf-8"))
    papers = B.load_all()[1]
    L = B.layout(tax, papers)

    def px(v):
        return Emu(int(round(v * PX)))

    def hx(v):
        """SVG colours carry a leading '#'; python-pptx wants bare hex."""
        return v.lstrip("#").upper()

    prs = Presentation()
    prs.slide_width = px(L["W"])
    prs.slide_height = px(L["H"])
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    def shape(kind, x, y, w, h, fill, line, rx):
        if kind == "dot":
            shp = slide.shapes.add_shape(MSO_SHAPE.OVAL, px(x), px(y), px(w), px(h))
        else:
            shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                         px(x), px(y), px(w), px(h))
            try:
                shp.adjustments[0] = min(0.5, rx / max(w, h) * 2.2)
            except Exception:
                pass
        shp.fill.solid()
        shp.fill.fore_color.rgb = RGBColor.from_string(hx(fill))
        if line:
            shp.line.color.rgb = RGBColor.from_string(hx(line))
            shp.line.width = Pt(0.75)
        else:
            shp.line.fill.background()
        shp.shadow.inherit = False
        return shp

    # nestled containers: bands first, then the inner leaf groups
    for p in L["panels"]:
        shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                     px(p["x"]), px(p["y"]), px(p["w"]), px(p["h"]))
        try:
            shp.adjustments[0] = min(0.5, p["rx"] / max(p["w"], p["h"]) * 2.2)
        except Exception:
            pass
        shp.fill.solid()
        shp.fill.fore_color.rgb = RGBColor.from_string(hx(p["fill"]))
        if p["stroke"]:
            shp.line.color.rgb = RGBColor.from_string(hx(p["stroke"]))
            shp.line.width = Pt(1)
        else:
            shp.line.fill.background()
        shp.shadow.inherit = False

    # connectors as freeform polylines
    def line(x1, y1, x2, y2, color, width=1.0):
        builder = slide.shapes.build_freeform(px(x1), px(y1))
        builder.add_line_segments([(px(x2), px(y2))], close=False)
        ln = builder.convert_to_shape()
        ln.fill.background()
        ln.line.color.rgb = RGBColor.from_string(hx(color))
        ln.line.width = Pt(width)
        ln.shadow.inherit = False

    for c in L["conns"]:
        line(c["x1"], c["y1"], c["x2"], c["y2"], c["color"])

    # hierarchical-relation arrows, with an arrowhead at the target end
    for a in L.get("arrows", []):
        x1, x2, ay = a["x1"], a["x2"], a["y"]
        tip = x2 - 7 if a["fwd"] else x2 + 7
        line(x1, ay, tip, ay, a["color"], width=1.2)
        head = MSO_SHAPE.ISOSCELES_TRIANGLE
        hx_, hy_, hw_, hh_ = (x2 - 5, ay - 4, 10, 8)
        tri = slide.shapes.add_shape(head, px(hx_), px(hy_), px(hw_), px(hh_))
        tri.rotation = 90 if a["fwd"] else 270
        tri.fill.solid()
        tri.fill.fore_color.rgb = RGBColor.from_string(hx(a["color"]))
        tri.line.fill.background()
        tri.shadow.inherit = False

    for b in L["boxes"]:
        shape(b["kind"], b["x"], b["y"], b["w"], b["h"],
              b["fill"], b["stroke"], b["rx"])

    for t in L["texts"]:
        tb = slide.shapes.add_textbox(px(t["x"] - 4), px(t["y"] - 15),
                                      px(B.text_w(t["s"], t["size"]) + 16), px(24))
        tf = tb.text_frame
        tf.word_wrap = False
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        para = tf.paragraphs[0]
        para.alignment = {"start": PP_ALIGN.LEFT, "middle": PP_ALIGN.CENTER,
                          "end": PP_ALIGN.RIGHT}[t["anchor"]]
        run = para.add_run()
        run.text = t["s"]
        run.font.size = Pt(t["size"] * 0.75)
        run.font.bold = t["weight"] >= 600
        run.font.color.rgb = RGBColor.from_string(hx(t["color"]))
        run.font.name = "Helvetica"

    prs.save(str(PPTX))
    return PPTX


def main():
    if not SVG.exists():
        sys.exit("run build.py first")
    p = make_png()
    print(f"{p.relative_to(ROOT)}  ({p.stat().st_size // 1024} KB)")
    q = make_pptx()
    print(f"{q.relative_to(ROOT)}  ({q.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
