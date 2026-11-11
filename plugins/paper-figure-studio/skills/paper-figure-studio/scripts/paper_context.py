#!/usr/bin/env python3
"""Scan a LaTeX paper project to extract venue widths, macros, equations, and figure inventory."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

VENUE_SPECS = {
    "icml": {"textwidth_in": 6.75, "columnwidth_in": 3.25, "double_canvas_in": 13.5, "single_canvas_in": 6.5},
    "neurips": {"textwidth_in": 5.50, "columnwidth_in": 5.50, "double_canvas_in": 11.0, "single_canvas_in": 11.0},
    "iclr": {"textwidth_in": 5.50, "columnwidth_in": 5.50, "double_canvas_in": 11.0, "single_canvas_in": 11.0},
    "cvpr": {"textwidth_in": 6.875, "columnwidth_in": 3.25, "double_canvas_in": 13.75, "single_canvas_in": 6.5},
    "acl": {"textwidth_in": 6.30, "columnwidth_in": 3.03, "double_canvas_in": 12.6, "single_canvas_in": 6.1},
    "ieee": {"textwidth_in": 7.16, "columnwidth_in": 3.50, "double_canvas_in": 14.3, "single_canvas_in": 7.0},
    "article_1in": {"textwidth_in": 6.50, "columnwidth_in": 6.50, "double_canvas_in": 13.0, "single_canvas_in": 6.5},
}


def detect_venue(tex_text: str) -> tuple[str, dict]:
    lower = tex_text.lower()
    for key in ("icml", "neurips", "iclr", "cvpr", "acl", "emnlp", "naacl", "ieee"):
        if re.search(rf"\\usepackage(?:\[[^\]]*\])?\{{[^}}]*{key}[^}}]*\}}", lower) or (
            key == "ieee" and "ieeetran" in lower
        ):
            mapped = "acl" if key in ("emnlp", "naacl") else key
            return mapped, VENUE_SPECS[mapped]
    return "article_1in", VENUE_SPECS["article_1in"]


def extract_macros(tex_files: list[Path]) -> dict[str, str]:
    macros: dict[str, str] = {}
    pat = re.compile(r"\\newcommand\{\\([A-Za-z0-9]+)\}(?:\[\d+\])?\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}")
    for fp in tex_files:
        try:
            content = fp.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in pat.finditer(content):
            name, val = m.group(1), m.group(2).strip()
            if len(val) <= 140:
                macros[name] = val
    return macros


def scan_project(project_dir: Path) -> dict:
    tex_files = sorted(
        p for p in project_dir.rglob("*.tex")
        if not any(part.startswith(".") or part in ("node_modules", "__pycache__", "dist") for part in p.parts)
    )
    main_candidates = [p for p in tex_files if "\\documentclass" in p.read_text(encoding="utf-8", errors="replace")]
    main_tex = main_candidates[0] if main_candidates else (tex_files[0] if tex_files else None)

    main_content = main_tex.read_text(encoding="utf-8", errors="replace") if main_tex else ""
    venue, spec = detect_venue(main_content)

    title_m = re.search(r"\\title\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", main_content, re.S)
    raw_title = re.sub(r"\s+", " ", title_m.group(1)).strip() if title_m else ""

    sections = []
    equations = []
    figures = []
    for fp in tex_files:
        txt = fp.read_text(encoding="utf-8", errors="replace")
        for sm in re.finditer(r"\\(section|subsection)\{([^}]+)\}", txt):
            sections.append({"file": str(fp.relative_to(project_dir)), "level": sm.group(1), "title": sm.group(2).strip()})
        for em in re.finditer(r"\\begin\{(equation\*?|align\*?)\}(.*?)\\end\{\1\}", txt, re.S):
            eq_clean = re.sub(r"\s+", " ", em.group(2)).strip()
            equations.append({"file": str(fp.relative_to(project_dir)), "latex": eq_clean[:260]})
        for fm in re.finditer(r"\\begin\{(figure\*?)\}(.*?)\\end\{\1\}", txt, re.S):
            body = fm.group(2)
            lbl = re.search(r"\\label\{([^}]+)\}", body)
            inc = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", body)
            has_tikz = "\\begin{tikzpicture}" in body
            figures.append({
                "file": str(fp.relative_to(project_dir)),
                "env": fm.group(1),
                "label": lbl.group(1) if lbl else "",
                "includes": inc,
                "inline_tikz": has_tikz,
            })

    macros = extract_macros(tex_files)
    paper_dir = main_tex.parent if main_tex else project_dir

    return {
        "project_dir": str(project_dir.resolve()),
        "paper_dir": str(paper_dir.resolve()),
        "main_tex": str(main_tex.resolve()) if main_tex else None,
        "detected_venue": venue,
        "layout_spec": spec,
        "title": raw_title,
        "sections": sections[:30],
        "equations": equations[:15],
        "existing_figures": figures,
        "macros": macros,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract LaTeX paper layout, macros, and equation context.")
    ap.add_argument("--project-dir", required=True, help="Root or paper/ directory of the target paper project.")
    ap.add_argument("--out", help="Optional JSON output file path.")
    args = ap.parse_args()

    info = scan_project(Path(args.project_dir))
    payload = json.dumps(info, ensure_ascii=False, indent=2)
    if args.out:
        out_p = Path(args.out)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(payload, encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
