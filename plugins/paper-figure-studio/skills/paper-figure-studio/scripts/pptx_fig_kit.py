#!/usr/bin/env python3
"""
pptx_fig_kit.py — Native Editable PPTX + OOXML Math SDK for Top-Conference Figures (ICML/NeurIPS/ICLR/ACL).

Design principles:
1. 2.0x Print-Scale Law:
   - Double-column figure* (6.75in print) -> 13.5in PPT canvas (0.5x scale: 14pt PPT = 7pt print, 16pt = 8pt).
   - Single-column figure  (3.25in print) -> 6.5in PPT canvas  (0.5x scale: 14pt PPT = 7pt print).
2. 100% Native Editable Objects:
   - Shapes, rounded zones, connectors, matrices, and OOXML `baseline` math runs (`Cambria Math`) remain
     natively clickable and editable in Microsoft PowerPoint, WPS Office, and LibreOffice Impress.
3. Strict ECMA-376 XML Hygiene:
   - Strips default Office theme shadows (`<a:effectLst/>`).
   - Appends `<a:headEnd>` / `<a:tailEnd>` in valid `CT_LineProperties` child order after fill & dash.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Sequence
from lxml import etree
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

DRAWINGML_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
PML_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"

# Colorblind-safe, high-contrast academic palette (zero gray-background-with-black-text!)
PALETTE = {
    # Surfaces (pastel tints, high luminance >= 92% so dark ink has > 10:1 contrast)
    "white": (255, 255, 255),
    "canvas_ice": (246, 250, 254),
    "zone_blue": (239, 246, 255),
    "zone_mint": (238, 250, 246),
    "zone_amber": (254, 248, 235),
    "zone_coral": (254, 242, 241),
    "zone_lavender": (245, 242, 253),
    "pill_blue": (219, 234, 254),
    "pill_teal": (209, 242, 235),
    "pill_amber": (254, 235, 200),
    "pill_coral": (254, 220, 218),
    "pill_purple": (233, 224, 250),
    # Strokes & Accents
    "ink": (24, 33, 47),
    "ink_soft": (62, 74, 92),
    "muted": (100, 112, 128),
    "border_blue": (147, 184, 232),
    "border_mint": (134, 201, 186),
    "border_amber": (228, 178, 106),
    "border_coral": (226, 146, 140),
    "border_purple": (176, 154, 218),
    "blue": (37, 99, 178),
    "navy": (28, 58, 99),
    "teal": (21, 128, 114),
    "amber": (194, 112, 22),
    "coral": (198, 66, 58),
    "purple": (118, 70, 166),
}

LATEX_SYMBOLS = [
    (r"\varepsilon", "ε"), (r"\epsilon", "ϵ"), (r"\alpha", "α"), (r"\beta", "β"),
    (r"\gamma", "γ"), (r"\delta", "δ"), (r"\theta", "θ"), (r"\lambda", "λ"),
    (r"\mu", "μ"), (r"\pi", "π"), (r"\rho", "ρ"), (r"\sigma", "σ"),
    (r"\tau", "τ"), (r"\phi", "φ"), (r"\omega", "ω"), (r"\Delta", "Δ"),
    (r"\Sigma", "Σ"), (r"\Omega", "Ω"), (r"\partial", "∂"), (r"\nabla", "∇"),
    (r"\mathbb{1}", "𝟙"), (r"\mathcal{P}", "𝒫"), (r"\mathcal{R}", "ℛ"),
    (r"\mathcal{C}", "𝒞"), (r"\mathcal{D}", "𝒟"), (r"\mathcal{F}", "ℱ"),
    (r"\mathcal{L}", "ℒ"), (r"\mathcal{N}", "𝒩"), (r"\mathcal{S}", "𝒮"),
    (r"\tfrac{1}{2}", "1/2"), (r"\frac{1}{2}", "1/2"), (r"\tfrac12", "1/2"),
    (r"\le", "≤"), (r"\leq", "≤"), (r"\ge", "≥"), (r"\geq", "≥"),
    (r"\ne", "≠"), (r"\neq", "≠"), (r"\approx", "≈"), (r"\equiv", "≡"),
    (r"\sim", "∼"), (r"\propto", "∝"), (r"\ll", "≪"), (r"\gg", "≫"),
    (r"\odot", "⊙"), (r"\oplus", "⊕"), (r"\otimes", "⊗"), (r"\cdot", "·"),
    (r"\times", "×"), (r"\pm", "±"), (r"\mp", "∓"), (r"\circ", "∘"),
    (r"\Rightarrow", "⇒"), (r"\mapsto", "↦"), (r"\rightarrow", "→"), (r"\to", "→"),
    (r"\leftarrow", "←"), (r"\leftrightarrow", "↔"),
    (r"\emptyset", "∅"), (r"\cap", "∩"), (r"\cup", "∪"),
    (r"\subseteq", "⊆"), (r"\subset", "⊂"), (r"\notin", "∉"), (r"\in", "∈"),
    (r"\sum", "∑"), (r"\prod", "∏"), (r"\infty", "∞"),
    (r"\checkmark", "✓"), (r"\timesmark", "✗"),
    (r"\{", "{"), (r"\}", "}"),
    (r"\qquad", "  "), (r"\quad", " "), (r"\;", " "), (r"\:", " "), (r"\,", " "), (r"\!", ""),
]

UPRIGHT_FUNCS = {"exp", "log", "ln", "sin", "cos", "tan", "max", "min", "sup", "inf", "arg", "lim", "iff", "Pr"}


def kill_shadow(shape) -> None:
    """Remove default PowerPoint & LibreOffice theme drop-shadows (`effectLst` + `style/effectRef`)."""
    shape.shadow.inherit = False
    el_root = shape._element
    spPr = el_root.spPr
    for el in spPr.findall(f"{{{DRAWINGML_NS}}}effectLst"):
        spPr.remove(el)
    etree.SubElement(spPr, f"{{{DRAWINGML_NS}}}effectLst")
    # Also zero out <p:style><a:effectRef idx="2"> so LibreOffice Impress renders crisp flat shapes
    p_style = el_root.find(f"{{{PML_NS}}}style")
    if p_style is not None:
        eff_ref = p_style.find(f"{{{DRAWINGML_NS}}}effectRef")
        if eff_ref is not None:
            eff_ref.set("idx", "0")


def _apply_combining_accents(expr: str) -> str:
    expr = re.sub(r"\\tilde\{([A-Za-z0-9])\}", lambda m: m.group(1) + "\u0303", expr)
    expr = re.sub(r"\\hat\{([A-Za-z0-9])\}", lambda m: m.group(1) + "\u0302", expr)
    expr = re.sub(r"\\bar\{([A-Za-z0-9])\}", lambda m: m.group(1) + "\u0304", expr)
    return expr


def parse_math_expr(expr: str) -> list[tuple[str, str, bool]]:
    """
    Convert a LaTeX-lite math string (e.g. r"R_i = a_i \\cdot (\\mathbb{1}[p_i \\ge 1/2] + d_i)")
    into a list of (text, mode, italic) tuples where mode in ('norm', 'sub', 'sup').
    """
    s = _apply_combining_accents(expr)
    # Unwrap \mathrm{...} / \text{...} into sentinel upright blocks
    upright_spans: list[str] = []

    def _save_upright(m: re.Match) -> str:
        idx = len(upright_spans)
        upright_spans.append(m.group(1))
        return f"\uE000{idx}\uE001"

    s = re.sub(r"\\(?:mathrm|text|operatorname)\{([^}]*)\}", _save_upright, s)
    for k, v in LATEX_SYMBOLS:
        s = s.replace(k, v)

    raw_tokens: list[tuple[str, str]] = []
    i = 0
    n = len(s)
    buf: list[str] = []

    def flush_buf() -> None:
        if buf:
            raw_tokens.append(("".join(buf), "norm"))
            buf.clear()

    while i < n:
        ch = s[i]
        if ch in ("_", "^") and i + 1 < n:
            flush_buf()
            mode = "sub" if ch == "_" else "sup"
            i += 1
            if s[i] == "{":
                depth = 1
                i += 1
                sub_chars: list[str] = []
                while i < n and depth > 0:
                    if s[i] == "{":
                        depth += 1
                    elif s[i] == "}":
                        depth -= 1
                        if depth == 0:
                            i += 1
                            break
                    if depth > 0:
                        sub_chars.append(s[i])
                        i += 1
                raw_tokens.append(("".join(sub_chars), mode))
            else:
                # Grab single character (+ combining accent if present)
                tok = s[i]
                i += 1
                while i < n and "\u0300" <= s[i] <= "\u036F":
                    tok += s[i]
                    i += 1
                raw_tokens.append((tok, mode))
        else:
            buf.append(ch)
            i += 1
    flush_buf()

    parts: list[tuple[str, str, bool]] = []
    token_re = re.compile(r"\uE000(\d+)\uE001|[A-Za-z]\u0303?|[A-Za-z]{2,}|[^A-Za-z\uE000\uE001]+")

    for seg, mode in raw_tokens:
        pos = 0
        while pos < len(seg):
            if seg[pos] == "\uE000":
                end_m = seg.find("\uE001", pos)
                if end_m != -1:
                    idx = int(seg[pos + 1 : end_m])
                    parts.append((upright_spans[idx], mode, False))
                    pos = end_m + 1
                    continue
            # Match multi-letter word vs single math variable
            word_m = re.match(r"[A-Za-z]+[\u0300-\u036F]*", seg[pos:])
            if word_m:
                w = word_m.group(0)
                base_alpha = re.sub(r"[\u0300-\u036F]", "", w)
                if base_alpha in UPRIGHT_FUNCS or len(base_alpha) >= 2:
                    parts.append((w, mode, False))
                else:
                    parts.append((w, mode, True))
                pos += len(w)
            else:
                non_m = re.match(r"[^A-Za-z\uE000]+", seg[pos:])
                chunk = non_m.group(0) if non_m else seg[pos]
                parts.append((chunk, mode, False))
                pos += len(chunk)

    # Merge adjacent identical (mode, italic) runs for clean OOXML
    merged: list[tuple[str, str, bool]] = []
    for txt, mode, ital in parts:
        if not txt:
            continue
        if merged and merged[-1][1] == mode and merged[-1][2] == ital:
            merged[-1] = (merged[-1][0] + txt, mode, ital)
        else:
            merged.append((txt, mode, ital))
    return merged


def configure_text_frame(
    shape,
    wrap: bool = True,
    pad_lr: float = 0.05,
    pad_tb: float = 0.03,
    v_align: MSO_ANCHOR = MSO_ANCHOR.MIDDLE,
):
    tf = shape.text_frame
    tf.word_wrap = wrap
    tf.margin_left = Inches(pad_lr)
    tf.margin_right = Inches(pad_lr)
    tf.margin_top = Inches(pad_tb)
    tf.margin_bottom = Inches(pad_tb)
    tf.vertical_anchor = v_align
    return tf


def append_run(
    paragraph,
    text: str,
    size: float = 13.0,
    bold: bool = False,
    italic: bool = False,
    color: tuple[int, int, int] = PALETTE["ink"],
    font_name: str = "Arial",
    mode: str = "norm",
):
    r = paragraph.add_run()
    r.text = text
    eff_size = size if mode == "norm" else round(size * 0.78, 1)
    r.font.size = Pt(eff_size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.name = font_name
    r.font.color.rgb = RGBColor(*color)
    if mode == "sup":
        r.font._element.set("baseline", "32000")
    elif mode == "sub":
        r.font._element.set("baseline", "-25000")
    return r


def set_math_runs(
    shape,
    parts: Sequence[tuple],
    size: float = 13.0,
    color: tuple[int, int, int] = PALETTE["ink"],
    align: PP_ALIGN = PP_ALIGN.CENTER,
    bold: bool = False,
    pad_lr: float = 0.03,
    pad_tb: float = 0.02,
) -> None:
    """
    Write native OOXML math/text runs into a shape.
    Each item in `parts` can be:
      - (text, mode, italic)
      - (text, mode, italic, custom_rgb)
      - (text, mode, italic, custom_rgb, custom_bold)
    """
    tf = configure_text_frame(shape, wrap=False, pad_lr=pad_lr, pad_tb=pad_tb)
    p = tf.paragraphs[0]
    p.alignment = align
    for item in parts:
        txt, mode, ital = item[0], item[1], item[2]
        c_rgb = item[3] if len(item) >= 4 and item[3] is not None else color
        b_flag = item[4] if len(item) >= 5 else bold
        has_math_glyph = ital or mode != "norm" or any(ord(ch) > 127 for ch in txt)
        fname = "Cambria Math" if has_math_glyph else "Arial"
        append_run(p, txt, size=size, bold=b_flag, italic=ital, color=c_rgb, font_name=fname, mode=mode)


class FigureCanvas:
    """High-level ICML/NeurIPS Oral figure builder backed by native `python-pptx` objects."""

    def __init__(
        self,
        width_in: float = 13.5,
        height_in: float = 5.0,
        bg_rgb: tuple[int, int, int] | None = PALETTE["white"],
    ) -> None:
        self.width_in = width_in
        self.height_in = height_in
        self.prs = Presentation()
        self.prs.slide_width = Inches(width_in)
        self.prs.slide_height = Inches(height_in)
        self.slide = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        if bg_rgb is not None:
            bg = self.slide.background
            fill = bg.fill
            fill.solid()
            fill.fore_color.rgb = RGBColor(*bg_rgb)

    def add_box(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        fill_rgb: tuple[int, int, int] | None = PALETTE["white"],
        line_rgb: tuple[int, int, int] | None = PALETTE["ink_soft"],
        line_pt: float = 1.3,
        rounded: bool = True,
        radius: float = 0.08,
        dashed: bool = False,
        text: str | None = None,
        size: float = 13.5,
        bold: bool = False,
        italic: bool = False,
        color: tuple[int, int, int] = PALETTE["ink"],
        align: PP_ALIGN = PP_ALIGN.CENTER,
        v_align: MSO_ANCHOR = MSO_ANCHOR.MIDDLE,
        wrap: bool = True,
        pad_lr: float = 0.06,
        pad_tb: float = 0.03,
        font_name: str = "Arial",
    ):
        st = MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE
        sh = self.slide.shapes.add_shape(st, Inches(x), Inches(y), Inches(w), Inches(h))
        kill_shadow(sh)
        if rounded and hasattr(sh, "adjustments") and len(sh.adjustments) > 0:
            sh.adjustments[0] = max(0.01, min(0.5, radius))
        if fill_rgb is None:
            sh.fill.background()
        else:
            sh.fill.solid()
            sh.fill.fore_color.rgb = RGBColor(*fill_rgb)
        if line_rgb is None:
            sh.line.fill.background()
        else:
            sh.line.color.rgb = RGBColor(*line_rgb)
            sh.line.width = Pt(line_pt)
            if dashed:
                sh.line.dash_style = MSO_LINE_DASH_STYLE.DASH
        if text is not None:
            tf = configure_text_frame(sh, wrap=wrap, pad_lr=pad_lr, pad_tb=pad_tb, v_align=v_align)
            lines = text.split("\n")
            for idx, ln_txt in enumerate(lines):
                p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
                p.alignment = align
                append_run(p, ln_txt, size=size, bold=bold, italic=italic, color=color, font_name=font_name)
        return sh

    def add_rich_box(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        lines: Sequence[Sequence[dict]],
        fill_rgb: tuple[int, int, int] | None = PALETTE["white"],
        line_rgb: tuple[int, int, int] | None = PALETTE["ink_soft"],
        line_pt: float = 1.3,
        rounded: bool = True,
        radius: float = 0.08,
        dashed: bool = False,
        align: PP_ALIGN = PP_ALIGN.LEFT,
        v_align: MSO_ANCHOR = MSO_ANCHOR.MIDDLE,
        wrap: bool = True,
        pad_lr: float = 0.08,
        pad_tb: float = 0.04,
        space_after_pt: float = 2.0,
    ):
        """
        Create a native box whose text_frame holds multiple styled lines (mixing bold headers,
        regular copy, colored badges, and inline LaTeX-lite math runs inside ONE draggable PPT shape).

        Each element of `lines` is a list of span dicts:
          {"text": "Header ", "size": 14, "bold": True, "color": PALETTE["navy"]}
          {"math": r"p_i \\ge 1 - \\varepsilon", "size": 13.5, "color": PALETTE["teal"]}
        """
        sh = self.add_box(
            x, y, w, h, fill_rgb=fill_rgb, line_rgb=line_rgb, line_pt=line_pt,
            rounded=rounded, radius=radius, dashed=dashed, text=None,
        )
        tf = configure_text_frame(sh, wrap=wrap, pad_lr=pad_lr, pad_tb=pad_tb, v_align=v_align)
        for l_idx, line_spans in enumerate(lines):
            p = tf.paragraphs[0] if l_idx == 0 else tf.add_paragraph()
            p.alignment = line_spans[0].get("align", align) if line_spans else align
            if l_idx < len(lines) - 1 and space_after_pt > 0:
                p.space_after = Pt(space_after_pt)
            for sp in line_spans:
                sz = float(sp.get("size", 13.0))
                col = sp.get("color", PALETTE["ink"])
                bld = bool(sp.get("bold", False))
                itl = bool(sp.get("italic", False))
                if "math" in sp:
                    for m_txt, m_mode, m_ital in parse_math_expr(sp["math"]):
                        has_m = m_ital or m_mode != "norm" or any(ord(c) > 127 for c in m_txt)
                        append_run(
                            p, m_txt, size=sz, bold=bld, italic=(m_ital or itl),
                            color=col, font_name=("Cambria Math" if has_m else "Arial"), mode=m_mode,
                        )
                else:
                    txt = str(sp.get("text", ""))
                    fname = sp.get("font", "Cambria Math" if any(ord(c) > 127 for c in txt) else "Arial")
                    append_run(p, txt, size=sz, bold=bld, italic=itl, color=col, font_name=fname, mode=sp.get("mode", "norm"))
        return sh

    def add_zone(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        fill_rgb: tuple[int, int, int] = PALETTE["zone_blue"],
        line_rgb: tuple[int, int, int] | None = PALETTE["border_blue"],
        line_pt: float = 1.4,
        dashed: bool = False,
        radius: float = 0.04,
        subcaption: str | None = None,
        subcaption_h: float = 0.34,
        subcaption_size: float = 14.5,
    ):
        """Add a soft pastel panel container with an optional `(a) ...` subcaption below it."""
        zone = self.add_box(
            x, y, w, h, fill_rgb=fill_rgb, line_rgb=line_rgb,
            line_pt=line_pt, rounded=True, radius=radius, dashed=dashed,
        )
        if subcaption:
            self.add_label(
                x, y + h + 0.04, w, subcaption_h, subcaption,
                size=subcaption_size, bold=True, color=PALETTE["ink"], align=PP_ALIGN.CENTER, wrap=False,
            )
        return zone

    def add_label(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        text: str,
        size: float = 13.5,
        bold: bool = False,
        italic: bool = False,
        color: tuple[int, int, int] = PALETTE["ink"],
        align: PP_ALIGN = PP_ALIGN.CENTER,
        wrap: bool = False,
        font_name: str = "Arial",
    ):
        tb = self.slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = configure_text_frame(tb, wrap=wrap, pad_lr=0.02, pad_tb=0.01)
        for idx, ln in enumerate(text.split("\n")):
            p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
            p.alignment = align
            append_run(p, ln, size=size, bold=bold, italic=italic, color=color, font_name=font_name)
        return tb

    def add_math_box(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        expr: str,
        size: float = 13.5,
        color: tuple[int, int, int] = PALETTE["ink"],
        fill_rgb: tuple[int, int, int] | None = None,
        line_rgb: tuple[int, int, int] | None = None,
        line_pt: float = 1.1,
        rounded: bool = True,
        radius: float = 0.12,
        align: PP_ALIGN = PP_ALIGN.CENTER,
        bold: bool = False,
    ):
        sh = self.add_box(
            x, y, w, h, fill_rgb=fill_rgb, line_rgb=line_rgb,
            line_pt=line_pt, rounded=rounded, radius=radius,
        )
        parts = parse_math_expr(expr)
        set_math_runs(sh, parts, size=size, color=color, align=align, bold=bold)
        return sh

    def add_circle(
        self,
        cx: float,
        cy: float,
        d: float,
        fill_rgb: tuple[int, int, int] | None = PALETTE["white"],
        line_rgb: tuple[int, int, int] | None = PALETTE["ink_soft"],
        line_pt: float = 1.8,
        text: str = "",
        text_rgb: tuple[int, int, int] = PALETTE["ink"],
        size: float = 12.5,
        bold: bool = True,
    ):
        ov = self.slide.shapes.add_shape(
            MSO_SHAPE.OVAL, Inches(cx - d / 2), Inches(cy - d / 2), Inches(d), Inches(d)
        )
        kill_shadow(ov)
        if fill_rgb is None:
            ov.fill.background()
        else:
            ov.fill.solid()
            ov.fill.fore_color.rgb = RGBColor(*fill_rgb)
        if line_rgb is None:
            ov.line.fill.background()
        else:
            ov.line.color.rgb = RGBColor(*line_rgb)
            ov.line.width = Pt(line_pt)
        if text:
            tf = configure_text_frame(ov, wrap=False, pad_lr=0.01, pad_tb=0.01)
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER
            append_run(p, text, size=size, bold=bold, color=text_rgb)
        return ov

    def add_step_badge(
        self,
        cx: float,
        cy: float,
        num: int | str,
        fill_rgb: tuple[int, int, int] = PALETTE["navy"],
        d: float = 0.34,
        size: float = 13.0,
    ):
        """Numbered anchor circle (1, 2, 3, 4) for clear closed-loop visual reading order."""
        return self.add_circle(
            cx, cy, d=d, fill_rgb=fill_rgb, line_rgb=PALETTE["white"],
            line_pt=1.2, text=str(num), text_rgb=PALETTE["white"], size=size, bold=True,
        )

    def add_arrow(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        color: tuple[int, int, int] = PALETTE["ink_soft"],
        pt: float = 1.8,
        arrow_end: bool = True,
        arrow_start: bool = False,
        dashed: bool = False,
        head_size: str = "med",
    ):
        conn = self.slide.shapes.add_connector(
            MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2)
        )
        kill_shadow(conn)
        conn.line.color.rgb = RGBColor(*color)
        conn.line.width = Pt(pt)
        if dashed:
            conn.line.dash_style = MSO_LINE_DASH_STYLE.DASH
        ln = conn.line._get_or_add_ln()
        for tag in ("headEnd", "tailEnd"):
            for old in ln.findall(f"{{{DRAWINGML_NS}}}{tag}"):
                ln.remove(old)
        if arrow_start:
            he = etree.SubElement(ln, f"{{{DRAWINGML_NS}}}headEnd")
            he.set("type", "triangle")
            he.set("w", head_size)
            he.set("len", head_size)
        if arrow_end:
            te = etree.SubElement(ln, f"{{{DRAWINGML_NS}}}tailEnd")
            te.set("type", "triangle")
            te.set("w", head_size)
            te.set("len", head_size)
        return conn

    def add_ortho_arrow(
        self,
        points: Sequence[tuple[float, float]],
        color: tuple[int, int, int] = PALETTE["ink_soft"],
        pt: float = 1.8,
        dashed: bool = False,
        arrow_end: bool = True,
        head_size: str = "med",
    ) -> list:
        """Draw a crisp multi-segment orthogonal polyline with arrowhead on the final segment."""
        segs = []
        n = len(points)
        for idx in range(n - 1):
            x1, y1 = points[idx]
            x2, y2 = points[idx + 1]
            is_last = idx == n - 2
            segs.append(
                self.add_arrow(
                    x1, y1, x2, y2, color=color, pt=pt,
                    arrow_end=(arrow_end and is_last), dashed=dashed, head_size=head_size,
                )
            )
        return segs

    def add_picture_fit(
        self,
        image_path: str | Path,
        x: float,
        y: float,
        box_w: float,
        box_h: float,
    ):
        """Place an image centered inside `(x, y, box_w, box_h)` preserving exact aspect ratio."""
        p = Path(image_path)
        with Image.open(p) as im:
            iw, ih = im.size
        scale = min(box_w / max(iw, 1), box_h / max(ih, 1))
        w = iw * scale
        h = ih * scale
        px = x + (box_w - w) / 2.0
        py = y + (box_h - h) / 2.0
        return self.slide.shapes.add_picture(str(p), Inches(px), Inches(py), width=Inches(w), height=Inches(h))

    def save(self, pptx_path: str | Path) -> Path:
        out = Path(pptx_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        self.prs.save(str(out))
        return out
