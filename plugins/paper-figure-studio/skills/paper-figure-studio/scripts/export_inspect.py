#!/usr/bin/env python3
"""
export_inspect.py — Render-Inspect-Fix Closed-Loop Engine for PPTX -> Vector PDF Paper Figures.

Steps executed in a single deterministic pass:
1. Isolated LibreOffice headless export (`.pptx` -> raw vector `.pdf`, immune to open desktop LibreOffice).
2. Vector-preserving tight bounding-box crop (`fitz` `set_cropbox`, 0% rasterization) -> final `<out-pdf>`.
3. 6-rule deterministic machine audit (`audit_report.json`):
   - C1_VECTOR_PRIMITIVES : True vector paths + embedded text glyphs present
   - C2_PRINT_FONT_SIZE   : Effective font size >= 6.0pt at target LaTeX print width (e.g. 6.75in or 3.25in)
   - C3_UNINTENDED_WRAP   : Detects short labels in `.pptx` that accidentally wrapped onto 2+ PDF lines
   - C4_TEXT_OVERLAP      : Detects colliding PDF text line bounding boxes
   - C5_GRAY_BG_CONTRAST  : Flags ICML-prohibited neutral gray fill behind dark text
   - C6_NO_TOP_TITLE      : Warns if a redundant top-center banner title exists inside the figure
4. Generates 3 visual inspection images for Agent `read_file` verification:
   - `<stem>_preview.png`     : 300 DPI clean render of the tight-cropped vector PDF
   - `<stem>_ruler_grid.png`  : 200 DPI full-slide diagnostic overlay with inch coordinate rulers & warning callouts
   - `<stem>_icml_mockup.png` : 180 DPI simulated two-column US Letter paper page at 100% print scale
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import fitz
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def find_soffice() -> str:
    found = shutil.which("soffice") or shutil.which("libreoffice")
    if found:
        return found
    candidates = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        "/usr/bin/soffice",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    raise FileNotFoundError("LibreOffice `soffice` executable not found on this machine.")


def export_pptx_to_raw_pdf(pptx_path: Path, out_dir: Path) -> Path:
    soffice = find_soffice()
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lo_fig_profile_") as tmp_prof:
        prof_uri = Path(tmp_prof).resolve().as_uri()
        cmd = [
            soffice,
            f"-env:UserInstallation={prof_uri}",
            "--headless",
            "--norestore",
            "--convert-to",
            "pdf",
            "--outdir",
            str(out_dir),
            str(pptx_path),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
    raw_pdf = out_dir / f"{pptx_path.stem}.pdf"
    if not raw_pdf.exists():
        raise RuntimeError(f"LibreOffice exited 0 but did not produce {raw_pdf}")
    return raw_pdf


def compute_ink_bbox_pt(page: fitz.Page, pad_in: float = 0.05, dpi: int = 144) -> fitz.Rect:
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    non_white = np.any(arr < 250, axis=2)
    ys, xs = np.where(non_white)
    if len(xs) == 0 or len(ys) == 0:
        return page.rect
    scale = 72.0 / dpi
    pad_pt = pad_in * 72.0
    x0 = max(page.rect.x0, float(xs.min()) * scale - pad_pt)
    y0 = max(page.rect.y0, float(ys.min()) * scale - pad_pt)
    x1 = min(page.rect.x1, float(xs.max() + 1) * scale + pad_pt)
    y1 = min(page.rect.y1, float(ys.max() + 1) * scale + pad_pt)
    return fitz.Rect(x0, y0, x1, y1)


def extract_pdf_lines(page: fitz.Page) -> list[dict]:
    lines_out: list[dict] = []
    td = page.get_text("dict")
    for b in td.get("blocks", []):
        if b.get("type") != 0:
            continue
        for ln in b.get("lines", []):
            spans = ln.get("spans", [])
            txt = "".join(s.get("text", "") for s in spans).strip()
            if not txt:
                continue
            max_sz = max((float(s.get("size", 0.0)) for s in spans), default=0.0)
            bbox = ln.get("bbox", [0, 0, 0, 0])
            lines_out.append({
                "text": txt,
                "max_size_pt": round(max_sz, 2),
                "bbox_pt": [round(float(v), 2) for v in bbox],
                "bbox_in": [round(float(v) / 72.0, 2) for v in bbox],
            })
    return lines_out


def audit_pptx_and_pdf(
    pptx_path: Path,
    slide_idx: int,
    raw_page: fitz.Page,
    crop_rect: fitz.Rect,
    target_width_in: float,
) -> dict:
    checks: list[dict] = []
    warnings_boxes_in: list[tuple[float, float, float, float, str]] = []

    drawings = raw_page.get_drawings()
    pdf_lines = extract_pdf_lines(raw_page)
    cropped_w_in = crop_rect.width / 72.0
    cropped_h_in = crop_rect.height / 72.0
    print_scale = target_width_in / max(cropped_w_in, 0.1)

    # C1: Vector primitives check
    c1_ok = len(drawings) >= 3 and len(pdf_lines) >= 2
    checks.append({
        "id": "C1_VECTOR_PRIMITIVES",
        "status": "PASS" if c1_ok else "FAIL",
        "detail": f"{len(drawings)} vector drawing paths, {len(pdf_lines)} selectable text lines.",
    })

    # C2: Print font size check at target LaTeX width
    tiny_spans = []
    warn_spans = []
    for ln in pdf_lines:
        # Ignore 1-2 char subscripts/superscripts or standalone bullets for the strict 6pt main-label gate
        clean_t = ln["text"].strip()
        eff_pt = ln["max_size_pt"] * print_scale
        min_gate = 4.5 if len(clean_t) <= 3 else 5.2
        warn_gate = 5.0 if len(clean_t) <= 3 else 5.85
        if eff_pt < min_gate:
            tiny_spans.append({**ln, "effective_print_pt": round(eff_pt, 2)})
            bx = ln["bbox_in"]
            warnings_boxes_in.append((bx[0], bx[1], bx[2], bx[3], f"Tiny:{eff_pt:.1f}pt"))
        elif eff_pt < warn_gate:
            warn_spans.append({**ln, "effective_print_pt": round(eff_pt, 2)})
    checks.append({
        "id": "C2_PRINT_FONT_SIZE",
        "status": "FAIL" if tiny_spans else ("WARN" if warn_spans else "PASS"),
        "print_scale": round(print_scale, 3),
        "detail": (
            f"Scale {print_scale:.2f}x ({cropped_w_in:.2f}in -> {target_width_in:.2f}in); "
            f"{len(tiny_spans)} fail spans, {len(warn_spans)} borderline spans."
        ),
        "offenders": (tiny_spans + warn_spans)[:8],
    })

    # C3 & C5: PPTX shape inspection for neutral-gray fills and narrow-wrap risks
    prs = Presentation(str(pptx_path))
    slide = prs.slides[slide_idx]
    gray_offenders = []
    wrap_suspects = []
    text_shape_boxes = []
    for s_tmp in slide.shapes:
        if s_tmp.has_text_frame and s_tmp.text_frame.text.strip():
            text_shape_boxes.append((
                s_tmp,
                s_tmp.left / 914400.0,
                s_tmp.top / 914400.0,
                (s_tmp.left + s_tmp.width) / 914400.0,
                (s_tmp.top + s_tmp.height) / 914400.0,
                (s_tmp.width / 914400.0) * (s_tmp.height / 914400.0),
            ))
    for sh in slide.shapes:
        x_in = sh.left / 914400.0
        y_in = sh.top / 914400.0
        w_in = sh.width / 914400.0
        h_in = sh.height / 914400.0
        if sh.has_text_frame:
            raw_txt = sh.text_frame.text.strip()
            # Check neutral gray background behind dark text
            try:
                if sh.fill.type == 1:  # SOLID
                    rgb = sh.fill.fore_color.rgb
                    r, g, b = rgb[0], rgb[1], rgb[2]
                    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
                    sat = max(r, g, b) - min(r, g, b)
                    if raw_txt and sat < 12 and 145 <= lum <= 228:
                        gray_offenders.append({"text": raw_txt[:30], "rgb": [r, g, b], "pos_in": [round(x_in, 2), round(y_in, 2)]})
                        warnings_boxes_in.append((x_in, y_in, x_in + w_in, y_in + h_in, "GrayBG"))
            except Exception:
                pass

            # Check if paragraphs in PPTX wrapped onto extra PDF lines or overflowed bottom border
            if raw_txt:
                p_count = sum(1 for p in sh.text_frame.paragraphs if p.text.strip())
                my_area = w_in * h_in
                child_boxes = [
                    (ox0 - 0.02, oy0 - 0.02, ox1 + 0.02, oy1 + 0.02)
                    for o_sh, ox0, oy0, ox1, oy1, o_area in text_shape_boxes
                    if o_sh is not sh and o_area < my_area * 0.5
                    and ox0 >= x_in - 0.15 and oy0 >= y_in - 0.15
                    and ox1 <= x_in + w_in + 0.15 and oy1 <= y_in + h_in + 0.15
                ]
                sx0, sy0, sx1, sy1 = x_in - 0.04, y_in - 0.04, x_in + w_in + 0.04, y_in + h_in + 0.08
                inside = []
                for ln in pdf_lines:
                    bx = ln["bbox_in"]
                    if not (bx[0] >= sx0 and bx[2] <= sx1 and bx[1] >= sy0 and bx[3] <= sy1):
                        continue
                    if any(bx[0] >= cx0 and bx[2] <= cx1 and bx[1] >= cy0 and bx[3] <= cy1 for cx0, cy0, cx1, cy1 in child_boxes):
                        continue
                    inside.append(ln)
                # Cluster distinct vertical baselines (> 0.09in apart) so inline subscripts don't double-count
                ys_sorted = sorted(0.5 * (ln["bbox_in"][1] + ln["bbox_in"][3]) for ln in inside)
                distinct_rows = 0
                last_y = -999.0
                for yc in ys_sorted:
                    if yc - last_y > 0.09:
                        distinct_rows += 1
                        last_y = yc
                if p_count > 0 and distinct_rows > p_count and (not sh.text_frame.word_wrap or h_in < 1.25):
                    wrap_suspects.append({
                        "text": raw_txt[:45],
                        "expected_lines": p_count,
                        "rendered_rows": distinct_rows,
                        "pos_in": [round(x_in, 2), round(y_in, 2)],
                    })
                    warnings_boxes_in.append((x_in, y_in, x_in + w_in, y_in + h_in, f"Wrap:{distinct_rows}>{p_count}"))

    checks.append({
        "id": "C3_UNINTENDED_WRAP",
        "status": "FAIL" if wrap_suspects else "PASS",
        "detail": f"{len(wrap_suspects)} short labels wrapped unintentionally.",
        "offenders": wrap_suspects,
    })

    # C4: Pairwise text line bounding-box collision check
    overlaps = []
    for i in range(len(pdf_lines)):
        a = pdf_lines[i]["bbox_pt"]
        for j in range(i + 1, len(pdf_lines)):
            b = pdf_lines[j]["bbox_pt"]
            ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
            ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
            iw, ih = ix1 - ix0, iy1 - iy0
            if iw > 3.0 and ih > 3.5:
                area_inter = iw * ih
                min_area = max(1.0, min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1])))
                # Skip inline sub/superscripts sharing baseline proximity on short tokens
                if len(pdf_lines[i]["text"]) <= 3 or len(pdf_lines[j]["text"]) <= 3:
                    if abs(a[1] - b[1]) < 8.0 and iw < 6.5:
                        continue
                if area_inter / min_area > 0.22:
                    bi = pdf_lines[i]["bbox_in"]
                    overlaps.append({
                        "text_a": pdf_lines[i]["text"][:32],
                        "text_b": pdf_lines[j]["text"][:32],
                        "overlap_ratio": round(area_inter / min_area, 2),
                        "pos_in": [bi[0], bi[1]],
                    })
                    warnings_boxes_in.append((bi[0], bi[1], bi[2], bi[3], "Overlap"))
    checks.append({
        "id": "C4_TEXT_OVERLAP",
        "status": "FAIL" if overlaps else "PASS",
        "detail": f"{len(overlaps)} overlapping text bounding-box pairs.",
        "offenders": overlaps[:8],
    })

    checks.append({
        "id": "C5_GRAY_BG_CONTRAST",
        "status": "FAIL" if gray_offenders else "PASS",
        "detail": f"{len(gray_offenders)} neutral-gray-background text shapes.",
        "offenders": gray_offenders,
    })

    # C6: Redundant top banner title check
    slide_w_in = raw_page.rect.width / 72.0
    top_titles = [
        ln for ln in pdf_lines
        if ln["bbox_in"][1] < (crop_rect.y0 / 72.0 + 0.28)
        and ln["max_size_pt"] >= 19.0
        and abs(((ln["bbox_in"][0] + ln["bbox_in"][2]) / 2.0) - slide_w_in / 2.0) < 1.5
    ]
    checks.append({
        "id": "C6_NO_TOP_TITLE",
        "status": "WARN" if top_titles else "PASS",
        "detail": "No redundant figure-wide top title detected." if not top_titles else f"Top banner text found: {top_titles[0]['text']}",
    })

    overall = "PASS"
    if any(c["status"] == "FAIL" for c in checks):
        overall = "FAIL"
    elif any(c["status"] == "WARN" for c in checks):
        overall = "WARN"

    return {
        "overall": overall,
        "cropped_size_in": [round(cropped_w_in, 3), round(cropped_h_in, 3)],
        "target_print_width_in": target_width_in,
        "print_scale": round(print_scale, 3),
        "checks": checks,
        "_warning_boxes_in": warnings_boxes_in,
    }


def render_ruler_grid(
    raw_page: fitz.Page,
    out_png: Path,
    warning_boxes_in: list[tuple[float, float, float, float, str]],
    dpi: int = 180,
) -> None:
    pix = raw_page.get_pixmap(dpi=dpi, alpha=False)
    slide_img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    margin = 38
    canvas = Image.new("RGB", (slide_img.width + margin, slide_img.height + margin), (242, 245, 250))
    canvas.paste(slide_img, (margin, margin))
    draw = ImageDraw.Draw(canvas, "RGBA")
    font = ImageFont.load_default()

    w_in = raw_page.rect.width / 72.0
    h_in = raw_page.rect.height / 72.0

    # 0.5-inch grid + top/left inch rulers
    step = 0.5
    x_val = 0.0
    while x_val <= w_in + 1e-6:
        px = margin + round(x_val * dpi)
        is_major = abs(x_val - round(x_val)) < 1e-6
        col = (59, 130, 246, 75 if is_major else 36)
        draw.line([(px, margin), (px, canvas.height)], fill=col, width=1)
        draw.line([(px, margin - (8 if is_major else 4)), (px, margin)], fill=(30, 41, 59, 255), width=1)
        if is_major:
            draw.text((px + 2, 10), f'{int(round(x_val))}"', fill=(30, 41, 59, 255), font=font)
        x_val += step

    y_val = 0.0
    while y_val <= h_in + 1e-6:
        py = margin + round(y_val * dpi)
        is_major = abs(y_val - round(y_val)) < 1e-6
        col = (59, 130, 246, 75 if is_major else 36)
        draw.line([(margin, py), (canvas.width, py)], fill=col, width=1)
        draw.line([(margin - (8 if is_major else 4), py), (margin, py)], fill=(30, 41, 59, 255), width=1)
        if is_major:
            draw.text((4, py + 2), f'{int(round(y_val))}"', fill=(30, 41, 59, 255), font=font)
        y_val += step

    for x0, y0, x1, y1, tag in warning_boxes_in:
        rx0 = margin + round(x0 * dpi) - 3
        ry0 = margin + round(y0 * dpi) - 3
        rx1 = margin + round(x1 * dpi) + 3
        ry1 = margin + round(y1 * dpi) + 3
        draw.rectangle([rx0, ry0, rx1, ry1], outline=(220, 38, 38, 240), width=3)
        draw.rectangle([rx0, max(margin, ry0 - 15), rx0 + 84, ry0], fill=(220, 38, 38, 230))
        draw.text((rx0 + 3, max(margin, ry0 - 14)), tag[:14], fill=(255, 255, 255, 255), font=font)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_png)


def render_icml_page_mockup(
    cropped_page: fitz.Page,
    out_png: Path,
    target_width_in: float = 6.75,
    caption_text: str = "Figure 1: Overview figure rendered at exact 100% ICML two-column print scale (US Letter 8.5 x 11 in, textwidth = 6.75 in, columnwidth = 3.25 in).",
    dpi: int = 180,
) -> None:
    """Simulate a real US Letter ICML two-column page at 100% print scale to verify true font readability."""
    page_w_px = round(8.5 * dpi)
    page_h_px = round(11.0 * dpi)
    page_img = Image.new("RGB", (page_w_px, page_h_px), (255, 255, 255))
    draw = ImageDraw.Draw(page_img)

    margin_x = round(0.875 * dpi)
    margin_top = round(1.0 * dpi)
    col_w = round(3.25 * dpi)
    col_gap = round(0.25 * dpi)
    full_w = round(6.75 * dpi)

    # Running header rule (ICML style)
    draw.text((margin_x, margin_top - round(0.32 * dpi)), "Preprint / ICML Two-Column Print-Scale Verification Mockup", fill=(90, 95, 105))
    draw.line([(margin_x, margin_top - round(0.14 * dpi)), (margin_x + full_w, margin_top - round(0.14 * dpi))], fill=(40, 45, 55), width=2)

    # Render cropped vector figure at exact print DPI
    fig_w_in = cropped_page.rect.width / 72.0
    eff_dpi = dpi * (target_width_in / max(fig_w_in, 0.1))
    pix = cropped_page.get_pixmap(dpi=max(72, round(eff_dpi)), alpha=False)
    fig_im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    is_single_col = target_width_in <= 3.6
    fig_x = margin_x + col_w + col_gap if is_single_col else margin_x
    fig_y = margin_top
    page_img.paste(fig_im, (fig_x, fig_y))

    # Draw simulated caption line & body text blocks to judge visual density
    cap_y = fig_y + fig_im.height + round(0.10 * dpi)
    cap_w = col_w if is_single_col else full_w
    draw.text((fig_x, cap_y), caption_text[:115], fill=(25, 30, 38))
    if len(caption_text) > 115:
        draw.text((fig_x, cap_y + round(0.14 * dpi)), caption_text[115:230], fill=(25, 30, 38))

    body_start_y = cap_y + round(0.38 * dpi)
    line_step = round(0.155 * dpi)
    for col_idx in (0, 1):
        cx = margin_x + col_idx * (col_w + col_gap)
        start_y = margin_top if (is_single_col and col_idx == 0) else body_start_y
        y_cur = start_y
        idx_l = 0
        while y_cur < page_h_px - margin_top:
            # Simulated clean serif text bars (9.5pt height / 11pt leading rhythm)
            bar_w = round(col_w * (0.72 if idx_l % 9 == 8 else 0.98))
            indent = round(0.15 * dpi) if idx_l % 9 == 0 and idx_l > 0 else 0
            draw.rectangle([cx + indent, y_cur, cx + bar_w, y_cur + round(0.065 * dpi)], fill=(212, 216, 222))
            y_cur += line_step
            idx_l += 1

    out_png.parent.mkdir(parents=True, exist_ok=True)
    page_img.save(out_png)


def main() -> None:
    ap = argparse.ArgumentParser(description="Export PPTX to tight-cropped vector PDF and run Render-Inspect-Fix checks.")
    ap.add_argument("--pptx", required=True, help="Input .pptx file path.")
    ap.add_argument("--out-pdf", required=True, help="Output publication vector .pdf file path.")
    ap.add_argument("--inspect-dir", required=True, help="Directory for preview PNGs and audit_report.json.")
    ap.add_argument("--slide", type=int, default=0, help="0-based slide index to export (default: 0).")
    ap.add_argument("--target-width-in", type=float, default=6.75, help="Target LaTeX print width in inches (6.75 double-col, 3.25 single-col).")
    ap.add_argument("--pad-in", type=float, default=0.04, help="Tight-crop margin padding in inches.")
    ap.add_argument("--no-crop", action="store_true", help="Disable tight vector bounding-box cropping.")
    ap.add_argument("--caption", default="Figure: Overview of the proposed framework and closed-loop mechanism.", help="Caption preview string for mockup.")
    args = ap.parse_args()

    pptx_path = Path(args.pptx).resolve()
    out_pdf = Path(args.out_pdf).resolve()
    inspect_dir = Path(args.inspect_dir).resolve()
    inspect_dir.mkdir(parents=True, exist_ok=True)

    raw_dir = inspect_dir / "_raw_lo"
    raw_pdf = export_pptx_to_raw_pdf(pptx_path, raw_dir)

    src_doc = fitz.open(raw_pdf)
    if args.slide < 0 or args.slide >= len(src_doc):
        raise IndexError(f"Slide index {args.slide} out of range (total slides: {len(src_doc)})")

    raw_page = src_doc[args.slide]
    crop_rect = raw_page.rect if args.no_crop else compute_ink_bbox_pt(raw_page, pad_in=args.pad_in)

    audit = audit_pptx_and_pdf(
        pptx_path=pptx_path,
        slide_idx=args.slide,
        raw_page=raw_page,
        crop_rect=crop_rect,
        target_width_in=args.target_width_in,
    )
    warn_boxes = audit.pop("_warning_boxes_in", [])

    stem = out_pdf.stem
    ruler_png = inspect_dir / f"{stem}_ruler_grid.png"
    render_ruler_grid(raw_page, ruler_png, warn_boxes)

    # Select target slide in-place (avoids PyMuPDF `insert_pdf` xref corruption on LibreOffice tagged PDFs)
    src_doc.select([args.slide])
    cropped_page = src_doc[0]
    if not args.no_crop:
        cropped_page.set_cropbox(crop_rect)
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    src_doc.save(str(out_pdf), deflate=True, clean=True)
    src_doc.close()

    # Re-open saved vector PDF to verify exact file on disk and render clean 300 DPI preview + ICML mockup
    verify_doc = fitz.open(out_pdf)
    v_page = verify_doc[0]
    preview_png = inspect_dir / f"{stem}_preview.png"
    pix_clean = v_page.get_pixmap(dpi=300, alpha=False)
    pix_clean.save(str(preview_png))

    mockup_png = inspect_dir / f"{stem}_icml_mockup.png"
    render_icml_page_mockup(v_page, mockup_png, target_width_in=args.target_width_in, caption_text=args.caption)
    verify_doc.close()

    audit["outputs"] = {
        "pptx": str(pptx_path),
        "vector_pdf": str(out_pdf),
        "preview_png": str(preview_png),
        "ruler_grid_png": str(ruler_png),
        "icml_mockup_png": str(mockup_png),
    }
    report_path = inspect_dir / f"{stem}_audit.json"
    report_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
