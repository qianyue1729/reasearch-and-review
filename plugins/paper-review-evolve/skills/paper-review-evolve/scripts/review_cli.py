#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
review_cli.py — Multi-Round Blind Peer-Review & Self-Evolution CLI (`paper-review-evolve`)

Subcommands:
  1. init          Initialize `.scratch/paper-review-evolve/review_ledger.json` for a paper project.
  2. prompts       Generate 3 zero-context, artifact-grounded PC blind review prompts for Round k.
  3. record        Record Round k scores & Major/Minor counts from 3 orthogonal reviewers, evaluate
                   monotonic convergence criteria, and render `REVIEW_REPORT.md`.
  4. audit         Run deterministic manuscript & PDF checks (abstract word count, page limits,
                   Overfull \\hbox, undefined refs/citations, forbidden patterns, and PDF metadata
                   anonymity with optional `--scrub`).
  5. debloat-check Run final-stage anti-bloat & presentation readiness checks (abstract conciseness,
                   table first-column & flagship-first ordering, figure assets, Oral doc check).
  6. status        Print current convergence ledger summary.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure UTF-8 console output on Windows PowerShell
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


VENUE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "sp": {
        "display_name": "IEEE S&P (Oakland)",
        "scale_max": 5.0,
        "accept_threshold": 4.0,
        "max_body_pages": 13,
        "max_total_pages": 18,
        "ideal_abstract_words": [150, 220],
        "max_abstract_words": 250,
        "max_overfull_pt": 8.0,
        "personas": [
            {
                "id": "R1_crypto_formal",
                "role": "IEEE S&P PC Reviewer (Crypto, FHE/MPC & Formal Security)",
                "focus": (
                    "Formal security definitions, semi-honest/malicious threat model boundaries, "
                    "cryptographic parameters (ring dimension, modulus chain, multiplicative depth, "
                    "bootstrapping/communication costs), theorem proofs, and composition guarantees."
                ),
            },
            {
                "id": "R2_sidechannel_dp",
                "role": "IEEE S&P PC Reviewer (Side-Channels, Privacy & Statistical Rigor)",
                "focus": (
                    "Information-theoretic and differential-privacy bounds, finite-sample confidence "
                    "intervals, adaptive adversary countermeasures, multi-seed variance, and tightness "
                    "of empirical vs. theoretical leakage bounds."
                ),
            },
            {
                "id": "R3_systems_artifact",
                "role": "IEEE S&P PC Reviewer (LLM Systems, Scale & Artifact Audit)",
                "focus": (
                    "Modern flagship model scaling (e.g., 14B-70B vs. toy 0.5B-1.5B models), cross-family "
                    "and out-of-distribution (OOD) generalization, end-to-end latency/throughput, "
                    "table/figure clarity, and 100% consistency between JSON data, scripts, and LaTeX prose."
                ),
            },
        ],
    },
    "ccs": {
        "display_name": "ACM CCS",
        "scale_max": 5.0,
        "accept_threshold": 4.0,
        "max_body_pages": 12,
        "max_total_pages": 18,
        "ideal_abstract_words": [150, 220],
        "max_abstract_words": 250,
        "max_overfull_pt": 8.0,
        "personas": [
            {
                "id": "R1_crypto_protocol",
                "role": "ACM CCS PC Reviewer (Cryptographic Protocols & Security Proofs)",
                "focus": "Formal threat model, protocol security proofs, parameter realism, and cryptographic overhead.",
            },
            {
                "id": "R2_attack_defense",
                "role": "ACM CCS PC Reviewer (Adaptive Attacks & Privacy Quantification)",
                "focus": "Adaptive adversary evaluation, statistical rigor, ablation studies, and privacy-utility tradeoffs.",
            },
            {
                "id": "R3_systems_repro",
                "role": "ACM CCS PC Reviewer (Systems Scalability & Artifact Audit)",
                "focus": "Real-world system benchmarks, flagship model scale, code-to-paper consistency, and presentation clarity.",
            },
        ],
    },
    "usenix": {
        "display_name": "USENIX Security",
        "scale_max": 5.0,
        "accept_threshold": 4.0,
        "max_body_pages": 13,
        "max_total_pages": 19,
        "ideal_abstract_words": [150, 220],
        "max_abstract_words": 250,
        "max_overfull_pt": 8.0,
        "personas": [
            {
                "id": "R1_security_foundations",
                "role": "USENIX Security PC Reviewer (Security Foundations & Threat Model)",
                "focus": "Threat model realism, formal security guarantees, and cryptographic/system invariants.",
            },
            {
                "id": "R2_empirical_attack",
                "role": "USENIX Security PC Reviewer (Empirical Evaluation & Adaptive Baselines)",
                "focus": "Attack/defense effectiveness across realistic distributions, adaptive baselines, and statistical confidence.",
            },
            {
                "id": "R3_systems_open_science",
                "role": "USENIX Security PC Reviewer (Systems Overhead & Open-Science Audit)",
                "focus": "End-to-end system performance, modern workload scale, artifact reproducibility, and paper readability.",
            },
        ],
    },
    "icml": {
        "display_name": "ICML / NeurIPS / ICLR",
        "scale_max": 10.0,
        "accept_threshold": 7.0,
        "max_body_pages": 9,
        "max_total_pages": 25,
        "ideal_abstract_words": [150, 220],
        "max_abstract_words": 250,
        "max_overfull_pt": 8.0,
        "personas": [
            {
                "id": "R1_theory_proofs",
                "role": "ML Top-Venue Reviewer (Theory, Convergence & Approximation Bounds)",
                "focus": "Mathematical rigor of theorems/propositions, tightness of bounds, and justification of assumptions.",
            },
            {
                "id": "R2_empirical_scaling",
                "role": "ML Top-Venue Reviewer (Large-Scale Empirical Baselines & OOD Generalization)",
                "focus": "Scaling up to modern flagship models, SOTA baselines, multi-seed error bars, and OOD benchmarks.",
            },
            {
                "id": "R3_systems_clarity",
                "role": "ML Top-Venue Reviewer (Wall-Clock Efficiency, Ablations & Visual Clarity)",
                "focus": "Wall-clock speedup vs. theoretical FLOPs, Figure 1 clarity, table organization, and artifact consistency.",
            },
        ],
    },
    "acl": {
        "display_name": "ACL / EMNLP",
        "scale_max": 5.0,
        "accept_threshold": 4.0,
        "max_body_pages": 8,
        "max_total_pages": 20,
        "ideal_abstract_words": [130, 200],
        "max_abstract_words": 230,
        "max_overfull_pt": 8.0,
        "personas": [
            {
                "id": "R1_methodology_validity",
                "role": "ACL ARR Action Editor (Methodology & Evaluation Validity)",
                "focus": "Soundness of formulation, formal guarantees, and avoidance of evaluation leakage or judge bias.",
            },
            {
                "id": "R2_scaling_generalization",
                "role": "ACL Senior Reviewer (Multi-Family Scaling & Task Generalization)",
                "focus": "Performance across diverse model families/sizes (up to 70B), domains, and comprehensive ablations.",
            },
            {
                "id": "R3_repro_clarity",
                "role": "ACL Reviewer (Reproducibility, Error Analysis & Presentation Quality)",
                "focus": "Data-to-table consistency, qualitative/quantitative error analysis, limitations section, and visual polish.",
            },
        ],
    },
    "osdi": {
        "display_name": "OSDI / SOSP",
        "scale_max": 5.0,
        "accept_threshold": 4.0,
        "max_body_pages": 12,
        "max_total_pages": 18,
        "ideal_abstract_words": [150, 220],
        "max_abstract_words": 250,
        "max_overfull_pt": 8.0,
        "personas": [
            {
                "id": "R1_arch_invariants",
                "role": "OSDI/SOSP PC Reviewer (System Architecture & Correctness Invariants)",
                "focus": "Core system abstractions, correctness/security invariants, and failure/corner-case handling.",
            },
            {
                "id": "R2_perf_scalability",
                "role": "OSDI/SOSP PC Reviewer (End-to-End Throughput, Tail Latency & Scaling)",
                "focus": "End-to-end latency breakdown, hardware utilization, scaling to production workloads, and baseline fairness.",
            },
            {
                "id": "R3_artifact_clarity",
                "role": "OSDI/SOSP PC Reviewer (Implementation Realism & Artifact Audit)",
                "focus": "Implementation completeness, microbenchmark vs. macrobenchmark alignment, and paper readability.",
            },
        ],
    },
}


def strip_latex_to_words(latex_text: str) -> List[str]:
    """Strip comments, common LaTeX commands, and collapse inline math to count plain words accurately."""
    lines = []
    for line in latex_text.splitlines():
        line_clean = re.sub(r"(?<!\\)%.*$", "", line)
        lines.append(line_clean)
    text = "\n".join(lines)
    # Collapse inline math $...$ into a single token so math formulas don't inflate word count
    text = re.sub(r"\$[^$]+\$", " MATH_TOKEN ", text)
    # Replace common formatting macros with their inner text
    text = re.sub(r"\\(?:textbf|textit|emph|texttt|textsc|underline)\{([^{}]*)\}", r" \1 ", text)
    text = re.sub(r"\\(?:cite|citep|citet|ref|eqref|autoref|label)\{[^{}]*\}", " ", text)
    # Replace remaining LaTeX commands (e.g., \S, \approx) with a space
    text = re.sub(r"\\[a-zA-Z@]+", " ", text)
    text = re.sub(r"[{}$~\\]", " ", text)
    words = [w for w in re.split(r"\s+", text.strip()) if re.search(r"[A-Za-z0-9]", w)]
    return words


def extract_abstract_from_tex(tex_content: str) -> str:
    """Extract content inside \\begin{abstract}...\\end{abstract}."""
    m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", tex_content, flags=re.DOTALL)
    if not m:
        return ""
    return m.group(1).strip()


def resolve_tex_inputs(tex_path: Path) -> str:
    """Read main.tex and inline one level of \\input{...} if files exist."""
    if not tex_path.exists():
        return ""
    base_dir = tex_path.parent
    raw = tex_path.read_text(encoding="utf-8", errors="replace")

    def repl(match: re.Match) -> str:
        rel = match.group(1).strip()
        cand = base_dir / rel
        if not cand.suffix:
            cand_tex = cand.with_suffix(".tex")
            if cand_tex.exists():
                cand = cand_tex
        if cand.exists() and cand.is_file():
            return f"\n% --- BEGIN INPUT {rel} ---\n" + cand.read_text(encoding="utf-8", errors="replace") + f"\n% --- END INPUT {rel} ---\n"
        return match.group(0)

    return re.sub(r"\\input\{([^{}]+)\}", repl, raw)


def scrub_pdf_in_place(pdf_path: Path) -> Dict[str, Any]:
    """Scrub PDF metadata, XMP XML, and PTEX.Fullbanner in-place for double-blind anonymity."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return {"scrubbed": False, "error": "PyMuPDF (fitz) not installed"}

    tmp_path = pdf_path.with_suffix(".scrub_tmp.pdf")
    doc = fitz.open(str(pdf_path))
    doc.set_metadata({})
    try:
        doc.del_xml_metadata()
    except Exception:
        pass
    doc.save(
        str(tmp_path),
        garbage=4,
        deflate=True,
        clean=True,
        no_new_id=True,
    )
    doc.close()

    raw = tmp_path.read_bytes()
    # Scrub PTEX.Fullbanner and non-UTC timezone offsets in CreationDate/ModDate
    raw = re.sub(rb"/PTEX\.Fullbanner\s*\([^)]*\)", b"", raw)
    raw = re.sub(
        rb"/(CreationDate|ModDate)\s*\(D:\d{14}[^)]*\)",
        rb"/\1 (D:19700101000000Z)",
        raw,
    )
    pdf_path.write_bytes(raw)
    try:
        tmp_path.unlink()
    except OSError:
        pass
    return {"scrubbed": True, "size_bytes": len(raw)}


def inspect_pdf(pdf_path: Path) -> Dict[str, Any]:
    """Inspect PDF page count, section start pages, and metadata anonymity."""
    info: Dict[str, Any] = {
        "exists": pdf_path.exists(),
        "total_pages": 0,
        "ethics_page": None,
        "references_page": None,
        "appendix_page": None,
        "inferred_body_pages": None,
        "metadata_leaks": [],
    }
    if not pdf_path.exists():
        return info

    raw_bytes = pdf_path.read_bytes()
    if re.search(rb"/PTEX\.Fullbanner\s*\(", raw_bytes):
        info["metadata_leaks"].append("Binary contains /PTEX.Fullbanner (...) TeX Live fingerprint")
    tz_matches = re.findall(rb"/(?:CreationDate|ModDate)\s*\(D:\d{14}([+-]\d{2}'\d{2}')\)", raw_bytes)
    if tz_matches:
        info["metadata_leaks"].append(
            f"Binary contains non-UTC timezone offset in CreationDate/ModDate: {tz_matches[0].decode('latin1', errors='replace')}"
        )

    try:
        import fitz  # PyMuPDF
    except ImportError:
        info["note"] = "PyMuPDF (fitz) not installed; skipped page text inspection"
        return info

    doc = fitz.open(str(pdf_path))
    info["total_pages"] = len(doc)
    meta = doc.metadata or {}
    for k in ("author", "creator", "producer", "title", "subject", "keywords"):
        val = (meta.get(k) or "").strip()
        if val:
            info["metadata_leaks"].append(f"PDF metadata[{k}] is non-empty: {val!r}")

    for idx in range(len(doc)):
        page_num = idx + 1
        text = doc[idx].get_text("text")
        if info["ethics_page"] is None and re.search(r"(?:^|\n)\s*(?:\d+(?:\.\d+)*\s+)?Ethics\s+Considerations\b|(?:^|\n)\s*Ethical\s+Considerations\b", text, re.IGNORECASE):
            info["ethics_page"] = page_num
        if info["references_page"] is None and re.search(r"(?:^|\n)\s*References\s*(?:\n|$)", text):
            info["references_page"] = page_num
        if info["appendix_page"] is None and re.search(r"(?:^|\n)\s*Appendix(?:\s+[A-Z]|\s*:|\s*\n)", text):
            info["appendix_page"] = page_num

    doc.close()

    # Infer main body pages: before Ethics Considerations or References
    cutoff_candidates = [p for p in (info["ethics_page"], info["references_page"], info["appendix_page"]) if p is not None]
    if cutoff_candidates:
        first_backmatter = min(cutoff_candidates)
        info["inferred_body_pages"] = first_backmatter
    else:
        info["inferred_body_pages"] = info["total_pages"]

    return info


def parse_latex_log(log_path: Path) -> Dict[str, Any]:
    """Parse LaTeX .log file for Overfull \\hbox, undefined references, and undefined citations."""
    res: Dict[str, Any] = {
        "exists": log_path.exists(),
        "max_overfull_pt": 0.0,
        "overfull_Occurrences": [],
        "undefined_references": [],
        "undefined_citations": [],
        "multiply_defined_labels": [],
    }
    if not log_path.exists():
        return res

    content = log_path.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r"Overfull \\hbox \(([0-9.]+)pt too wide\) in paragraph at lines ([0-9\-]+)", content):
        pt = float(m.group(1))
        lines = m.group(2)
        if pt > res["max_overfull_pt"]:
            res["max_overfull_pt"] = pt
        res["overfull_Occurrences"].append({"pt": pt, "lines": lines})

    for m in re.finditer(r"LaTeX Warning: Reference `([^']+)' on page [0-9]+ undefined", content):
        res["undefined_references"].append(m.group(1))

    for m in re.finditer(r"LaTeX Warning: Citation `([^']+)' on page [0-9]+ undefined", content):
        res["undefined_citations"].append(m.group(1))

    for m in re.finditer(r"LaTeX Warning: Label `([^']+)' multiply defined", content):
        res["multiply_defined_labels"].append(m.group(1))

    return res


def cmd_init(args: argparse.Namespace) -> int:
    venue_key = args.venue.lower()
    if venue_key not in VENUE_DEFAULTS:
        print(f"Error: unknown venue '{args.venue}'. Choose from: {', '.join(VENUE_DEFAULTS.keys())}", file=sys.stderr)
        return 1

    venue_cfg = VENUE_DEFAULTS[venue_key]
    evolve_dir = Path(args.evolve_dir).resolve()
    evolve_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = evolve_dir / "review_ledger.json"

    ledger: Dict[str, Any] = {
        "project_dir": str(Path(args.project_dir).resolve()),
        "tex_path": str(Path(args.tex).resolve()) if args.tex else "",
        "pdf_path": str(Path(args.pdf).resolve()) if args.pdf else "",
        "venue": venue_key,
        "venue_display_name": venue_cfg["display_name"],
        "scale_max": venue_cfg["scale_max"],
        "accept_threshold": args.accept_threshold if args.accept_threshold is not None else venue_cfg["accept_threshold"],
        "max_body_pages": args.max_body_pages if args.max_body_pages is not None else venue_cfg["max_body_pages"],
        "max_total_pages": args.max_total_pages if args.max_total_pages is not None else venue_cfg["max_total_pages"],
        "ideal_abstract_words": venue_cfg["ideal_abstract_words"],
        "max_abstract_words": venue_cfg["max_abstract_words"],
        "max_overfull_pt": venue_cfg["max_overfull_pt"],
        "exemplars": args.exemplar or [],
        "forbidden_patterns": args.forbid_pattern or [],
        "personas": venue_cfg["personas"],
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "rounds": [],
    }

    ledger_path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] Initialized paper-review-evolve ledger at: {ledger_path}")
    print(f"     Venue: {ledger['venue_display_name']} | Target Accept >= {ledger['accept_threshold']}/{ledger['scale_max']}")
    return 0


def cmd_prompts(args: argparse.Namespace) -> int:
    evolve_dir = Path(args.evolve_dir).resolve()
    ledger_path = evolve_dir / "review_ledger.json"
    if not ledger_path.exists():
        print(f"Error: ledger not found at {ledger_path}. Run `init` first.", file=sys.stderr)
        return 1

    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    round_num = args.round if args.round is not None else (len(ledger.get("rounds", [])) + 1)
    venue_name = ledger["venue_display_name"]
    scale_max = ledger["scale_max"]
    accept_thresh = ledger["accept_threshold"]
    tex_path = args.tex or ledger.get("tex_path") or "<path/to/main.tex>"
    pdf_path = args.pdf or ledger.get("pdf_path") or "<path/to/main.pdf>"
    exemplars = ledger.get("exemplars", [])
    exemplar_str = (
        "Recent venue exemplar papers to benchmark against:\n" + "\n".join(f"  - {ex}" for ex in exemplars)
        if exemplars
        else "Benchmark against the rigorous standards of recent (last 2 years) papers published at " + venue_name + "."
    )

    prompts_out: List[Dict[str, str]] = []
    for p in ledger["personas"]:
        prompt_text = (
            f"You are an independent, skeptical, and constructive Program Committee (PC) member for {venue_name}.\n"
            f"Your assigned specialist persona: **{p['role']}**.\n"
            f"Your specialist review focus: {p['focus']}\n\n"
            f"### Strict Zero-Context Blind Review Protocol\n"
            f"1. Evaluate the manuscript SOLELY from the current compiled artifacts on disk:\n"
            f"   - Compiled PDF: `{pdf_path}`\n"
            f"   - LaTeX Source: `{tex_path}`\n"
            f"   - Supporting scripts/JSON data in the workspace (verify that claims in prose/tables match raw JSON outputs).\n"
            f"2. Do NOT search for or read any prior review rounds, author notes, or conversation transcripts.\n"
            f"3. {exemplar_str}\n\n"
            f"### Required Review Output Format\n"
            f"- **Overall Score**: X.X / {scale_max} (where >= {accept_thresh} indicates clear Accept, and {scale_max} indicates Strong Accept / Oral caliber)\n"
            f"- **Confidence**: 1 to 5\n"
            f"- **Executive Summary** (1 concise paragraph summarizing the paper's core contribution and whether its claims are substantiated)\n"
            f"- **Key Strengths** (3-4 bullet points grounded in specific sections, theorems, or tables)\n"
            f"- **Major Weaknesses (Blocking Issues)**: List every blocking issue (0 if none). Classify each as:\n"
            f"  * `[Type-A: Experimental/Scale Gap]` (e.g., missing flagship scale, missing OOD benchmark, missing adaptive baseline)\n"
            f"  * `[Type-B: Theoretical/Proof Gap]` (e.g., unproved assumption, loose or mismatched bound)\n"
            f"  * `[Type-C: Scope/Threat-Model Overclaim]` (e.g., claim exceeds evaluated setting)\n"
            f"- **Minor Weaknesses & Presentation Polish**: Typography, abstract conciseness (150-220 words), table ordering, or figure readability issues.\n"
            f"- **Actionable Verification Questions for Authors**: Concrete items that would raise your score."
        )
        prompts_out.append(
            {
                "round": round_num,
                "persona_id": p["id"],
                "role": p["role"],
                "subagent_invocation": {
                    "TypeName": "research",
                    "Role": p["role"],
                    "Prompt": prompt_text,
                },
            }
        )

    out_json = evolve_dir / f"round_{round_num}_prompts.json"
    out_md = evolve_dir / f"round_{round_num}_prompts.md"
    out_json.write_text(json.dumps(prompts_out, indent=2, ensure_ascii=False), encoding="utf-8")

    md_lines = [
        f"# Round {round_num} Zero-Context Blind Review Prompts ({venue_name})",
        "",
        "> Launch all 3 subagents in parallel via `invoke_subagent(TypeName=\"research\", ...)` with clean context.",
        "",
    ]
    for item in prompts_out:
        md_lines.append(f"## {item['persona_id']} — {item['role']}")
        md_lines.append("```markdown")
        md_lines.append(item["subagent_invocation"]["Prompt"])
        md_lines.append("```")
        md_lines.append("")

    out_md.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"[OK] Generated Round {round_num} 3-persona blind review prompts:")
    print(f"     JSON: {out_json}")
    print(f"     MD:   {out_md}")
    return 0


def evaluate_convergence(ledger: Dict[str, Any]) -> Dict[str, Any]:
    rounds = ledger.get("rounds", [])
    if not rounds:
        return {
            "converged": False,
            "reason": "No review rounds recorded yet.",
        }

    latest = rounds[-1]
    scores = [float(r["score"]) for r in latest["reviews"]]
    majors = sum(int(r.get("majors", 0)) for r in latest["reviews"])
    mean_score = sum(scores) / len(scores) if scores else 0.0
    min_score = min(scores) if scores else 0.0
    accept_thresh = float(ledger.get("accept_threshold", 4.0))

    all_positive = all(s >= accept_thresh for s in scores)
    zero_majors = majors == 0

    delta_prev: Optional[float] = None
    delta_ok = False
    if len(rounds) >= 2:
        prev_scores = [float(r["score"]) for r in rounds[-2]["reviews"]]
        prev_mean = sum(prev_scores) / len(prev_scores) if prev_scores else 0.0
        delta_prev = abs(mean_score - prev_mean)
        delta_ok = delta_prev < 0.30

    converged = bool(all_positive and zero_majors and (delta_ok or min_score >= float(ledger.get("scale_max", 5.0)) - 0.25))
    reasons = []
    if not all_positive:
        reasons.append(f"min reviewer score {min_score:.2f} < accept threshold {accept_thresh:.2f}")
    if not zero_majors:
        reasons.append(f"{majors} blocking Major weakness(es) remain")
    if len(rounds) < 2 and min_score < float(ledger.get("scale_max", 5.0)) - 0.25:
        reasons.append("fewer than 2 rounds completed to verify score stability (|Δ| < 0.30)")
    elif not delta_ok and min_score < float(ledger.get("scale_max", 5.0)) - 0.25:
        reasons.append(f"mean score delta |Δ| = {delta_prev:.2f} >= 0.30 (still improving; run one confirmation round)")

    return {
        "converged": converged,
        "latest_round": latest["round"],
        "mean_score": round(mean_score, 2),
        "min_score": round(min_score, 2),
        "total_majors": majors,
        "delta_from_prev": round(delta_prev, 2) if delta_prev is not None else None,
        "reason": "All convergence criteria met (All Accept, 0 Majors, score stabilized)." if converged else "; ".join(reasons),
    }


def render_review_report_md(ledger: Dict[str, Any], conv: Dict[str, Any]) -> str:
    lines = [
        f"# 多轮独立盲审自进化报告 ({ledger.get('venue_display_name', '')})",
        "",
        f"- **当前收敛状态**: {'✅ **已收敛 (CONVERGED)**' if conv['converged'] else '🔄 **迭代演进中 (IN PROGRESS)**'}",
        f"- **判定说明**: {conv['reason']}",
        f"- **录用门槛**: 全员 `>= {ledger.get('accept_threshold')}/{ledger.get('scale_max')}` 且 `0 Major` 且连续两轮均分波动 `< 0.30`",
        "",
        "## 1. 盲审分数与缺陷演化总表",
        "",
        "| 轮次 | R1 (理论/密码学) | R2 (侧信道/统计) | R3 (系统/制品审计) | 平均分 | 较上轮 Δ | Major 总数 | Minor 总数 | 核心升级摘要 |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |",
    ]
    prev_mean: Optional[float] = None
    for r in ledger.get("rounds", []):
        revs = r.get("reviews", [])
        s_strs = [f"{float(x['score']):.1f}" for x in revs]
        while len(s_strs) < 3:
            s_strs.append("-")
        scores = [float(x["score"]) for x in revs]
        mean_val = sum(scores) / len(scores) if scores else 0.0
        delta_str = "—" if prev_mean is None else f"{mean_val - prev_mean:+.2f}"
        prev_mean = mean_val
        majors = sum(int(x.get("majors", 0)) for x in revs)
        minors = sum(int(x.get("minors", 0)) for x in revs)
        notes = (r.get("summary") or "").replace("|", "\\|")
        lines.append(
            f"| **R{r['round']}** | {s_strs[0]} | {s_strs[1]} | {s_strs[2]} | **{mean_val:.2f}** | `{delta_str}` | {majors} | {minors} | {notes} |"
        )

    lines.append("")
    lines.append("## 2. 分轮次审稿意见与真凭实据修补记录")
    lines.append("")
    for r in ledger.get("rounds", []):
        lines.append(f"### Round {r['round']} (均分 `{r['mean_score']:.2f}`, Major `{r['total_majors']}`, Minor `{r['total_minors']}`)")
        if r.get("summary"):
            lines.append(f"- **本轮核心动作**: {r['summary']}")
        for rev in r.get("reviews", []):
            lines.append(
                f"  - **{rev.get('role', rev.get('id'))}**: `{float(rev['score']):.1f}/{ledger.get('scale_max')}` "
                f"(Major: `{rev.get('majors', 0)}`, Minor: `{rev.get('minors', 0)}`)"
            )
        lines.append("")

    return "\n".join(lines)


def cmd_record(args: argparse.Namespace) -> int:
    evolve_dir = Path(args.evolve_dir).resolve()
    ledger_path = evolve_dir / "review_ledger.json"
    if not ledger_path.exists():
        print(f"Error: ledger not found at {ledger_path}. Run `init` first.", file=sys.stderr)
        return 1

    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    if len(args.scores) != 3:
        print("Error: --scores must provide exactly 3 floats (for R1, R2, R3).", file=sys.stderr)
        return 1
    majors_list = args.majors if args.majors else [0, 0, 0]
    minors_list = args.minors if args.minors else [0, 0, 0]
    if len(majors_list) != 3 or len(minors_list) != 3:
        print("Error: --majors and --minors must each provide 3 integers.", file=sys.stderr)
        return 1

    personas = ledger.get("personas", [])
    reviews_entry = []
    for idx in range(3):
        p_id = personas[idx]["id"] if idx < len(personas) else f"R{idx+1}"
        p_role = personas[idx]["role"] if idx < len(personas) else f"Reviewer {idx+1}"
        reviews_entry.append(
            {
                "id": p_id,
                "role": p_role,
                "score": float(args.scores[idx]),
                "majors": int(majors_list[idx]),
                "minors": int(minors_list[idx]),
            }
        )

    mean_score = sum(args.scores) / 3.0
    round_entry = {
        "round": args.round,
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "mean_score": round(mean_score, 2),
        "total_majors": sum(majors_list),
        "total_minors": sum(minors_list),
        "summary": args.summary or "",
        "reviews": reviews_entry,
    }

    # Replace existing round if same number, else append
    existing_rounds = [r for r in ledger.get("rounds", []) if r.get("round") != args.round]
    existing_rounds.append(round_entry)
    existing_rounds.sort(key=lambda x: x["round"])
    ledger["rounds"] = existing_rounds

    conv = evaluate_convergence(ledger)
    ledger["convergence"] = conv
    ledger_path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")

    report_md = render_review_report_md(ledger, conv)
    report_path = evolve_dir / "REVIEW_REPORT.md"
    report_path.write_text(report_md, encoding="utf-8")

    print(f"[OK] Recorded Round {args.round} -> Mean: {mean_score:.2f} | Majors: {sum(majors_list)} | Converged: {conv['converged']}")
    print(f"     Reason: {conv['reason']}")
    print(f"     Report: {report_path}")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    venue_key = (args.venue or "sp").lower()
    venue_cfg = VENUE_DEFAULTS.get(venue_key, VENUE_DEFAULTS["sp"])

    tex_path = Path(args.tex).resolve()
    pdf_path = Path(args.pdf).resolve() if args.pdf else tex_path.with_suffix(".pdf")
    log_path = Path(args.log).resolve() if args.log else tex_path.with_suffix(".log")

    max_abs_words = args.max_abstract_words or venue_cfg["max_abstract_words"]
    max_body_pages = args.max_body_pages or venue_cfg["max_body_pages"]
    max_total_pages = args.max_total_pages or venue_cfg["max_total_pages"]
    max_overfull_pt = args.max_overfull_pt if args.max_overfull_pt is not None else venue_cfg["max_overfull_pt"]

    checks: List[Dict[str, Any]] = []

    def add_check(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    # 1. TeX existence & Abstract word count
    if not tex_path.exists():
        add_check("tex_exists", False, f"TeX file not found: {tex_path}")
        full_tex = ""
    else:
        add_check("tex_exists", True, f"Found {tex_path.name}")
        raw_tex = tex_path.read_text(encoding="utf-8", errors="replace")
        full_tex = resolve_tex_inputs(tex_path)
        abs_raw = extract_abstract_from_tex(raw_tex) or extract_abstract_from_tex(full_tex)
        abs_words = strip_latex_to_words(abs_raw)
        w_count = len(abs_words)
        ideal_low, ideal_high = venue_cfg["ideal_abstract_words"]
        add_check(
            "abstract_word_count",
            100 <= w_count <= max_abs_words,
            f"Abstract word count = {w_count} words (ideal: {ideal_low}-{ideal_high}, hard max: {max_abs_words})",
        )

        # 2. Forbidden LaTeX formatting anti-patterns
        resize_col = re.findall(r"\\resizebox\{\\columnwidth\}", full_tex)
        add_check(
            "no_resizebox_columnwidth",
            len(resize_col) == 0,
            f"Found {len(resize_col)} occurrences of \\resizebox{{\\columnwidth}} (distorts table font sizes)",
        )
        baselinestretch = re.findall(r"\\renewcommand\{\\baselinestretch\}", full_tex)
        add_check(
            "no_baselinestretch_hack",
            len(baselinestretch) == 0,
            f"Found {len(baselinestretch)} occurrences of \\baselinestretch override",
        )

        # 3. User-specified forbidden legacy/toy patterns
        for pat in args.forbid_pattern or []:
            matches = re.findall(pat, full_tex)
            add_check(
                f"forbid_pattern:{pat}",
                len(matches) == 0,
                f"Pattern '{pat}' matched {len(matches)} time(s)",
            )

    # 4. LaTeX .log checks
    log_info = parse_latex_log(log_path)
    if log_info["exists"]:
        add_check(
            "overfull_hbox_limit",
            log_info["max_overfull_pt"] <= max_overfull_pt,
            f"Max Overfull \\hbox = {log_info['max_overfull_pt']:.2f}pt (limit <= {max_overfull_pt:.1f}pt)",
        )
        add_check(
            "no_undefined_references",
            len(log_info["undefined_references"]) == 0,
            f"Undefined references: {log_info['undefined_references']}" if log_info["undefined_references"] else "0 undefined references",
        )
        add_check(
            "no_undefined_citations",
            len(log_info["undefined_citations"]) == 0,
            f"Undefined citations: {log_info['undefined_citations']}" if log_info["undefined_citations"] else "0 undefined citations",
        )
        add_check(
            "no_multiply_defined_labels",
            len(log_info["multiply_defined_labels"]) == 0,
            f"Multiply-defined labels: {log_info['multiply_defined_labels']}" if log_info["multiply_defined_labels"] else "0 multiply-defined labels",
        )
    else:
        add_check("log_exists", False, f"LaTeX log file not found at {log_path}")

    # 5. Optional PDF scrub + PDF page & metadata anonymity checks
    scrub_result = None
    if args.scrub and pdf_path.exists():
        scrub_result = scrub_pdf_in_place(pdf_path)

    pdf_info = inspect_pdf(pdf_path)
    if pdf_info["exists"]:
        if pdf_info["total_pages"] > 0:
            add_check(
                "pdf_total_pages_limit",
                pdf_info["total_pages"] <= max_total_pages,
                f"Total pages = {pdf_info['total_pages']} (limit <= {max_total_pages})",
            )
        if pdf_info["inferred_body_pages"] is not None:
            add_check(
                "pdf_body_pages_limit",
                pdf_info["inferred_body_pages"] <= max_body_pages,
                f"Body ends on page {pdf_info['inferred_body_pages']} (limit <= {max_body_pages}; "
                f"ethics_p={pdf_info['ethics_page']}, ref_p={pdf_info['references_page']}, app_p={pdf_info['appendix_page']})",
            )
        add_check(
            "pdf_anonymous_metadata",
            len(pdf_info["metadata_leaks"]) == 0,
            "0 metadata/timezone/PTEX leaks" if not pdf_info["metadata_leaks"] else "; ".join(pdf_info["metadata_leaks"]),
        )
    else:
        add_check("pdf_exists", False, f"Compiled PDF not found at {pdf_path}")

    passed_count = sum(1 for c in checks if c["passed"])
    total_count = len(checks)
    all_passed = passed_count == total_count

    report = {
        "status": "PASS" if all_passed else "FAIL",
        "venue": venue_key,
        "passed": passed_count,
        "total": total_count,
        "tex_path": str(tex_path),
        "pdf_path": str(pdf_path),
        "scrub_result": scrub_result,
        "pdf_info": pdf_info,
        "log_summary": {
            "max_overfull_pt": log_info.get("max_overfull_pt"),
            "undefined_references_count": len(log_info.get("undefined_references", [])),
            "undefined_citations_count": len(log_info.get("undefined_citations", [])),
        },
        "checks": checks,
    }

    if args.output:
        out_path = Path(args.output).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[{report['status']}] Audit checks: {passed_count}/{total_count} passed.")
    for c in checks:
        mark = "PASS" if c["passed"] else "FAIL"
        print(f"  [{mark}] {c['check']}: {c['detail']}")
    if args.output:
        print(f"Saved JSON audit report to: {args.output}")

    return 0 if all_passed else 2


def cmd_debloat_check(args: argparse.Namespace) -> int:
    tex_path = Path(args.tex).resolve()
    if not tex_path.exists():
        print(f"Error: TeX file not found: {tex_path}", file=sys.stderr)
        return 1

    base_dir = tex_path.parent
    full_tex = resolve_tex_inputs(tex_path)
    abs_raw = extract_abstract_from_tex(full_tex)
    plain_abs_path = base_dir / "abstract_plain.txt"
    if plain_abs_path.exists():
        plain_lines = [
            ln for ln in plain_abs_path.read_text(encoding="utf-8", errors="replace").splitlines()
            if not re.match(r"^\s*(?:Title|Abstract)\s*:", ln, flags=re.IGNORECASE)
        ]
        abs_words = [w for w in re.split(r"\s+", "\n".join(plain_lines).strip()) if w]
    else:
        abs_words = strip_latex_to_words(abs_raw)
    w_count = len(abs_words)
    paren_count = len(re.findall(r"\([^()]{15,}\)", abs_raw))

    # Inspect tables and their first data row
    table_summaries: List[Dict[str, Any]] = []
    for m in re.finditer(r"\\begin\{table\*?\}(.*?)\\end\{table\*?\}", full_tex, flags=re.DOTALL):
        t_body = m.group(1)
        cap_m = re.search(r"\\caption\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", t_body)
        lab_m = re.search(r"\\label\{([^{}]+)\}", t_body)
        caption = (cap_m.group(1).strip() if cap_m else "Untitled").splitlines()[0][:80]
        label = lab_m.group(1).strip() if lab_m else "no-label"

        # Find rows after \midrule
        mid_m = re.search(r"\\midrule(.*?)(?:\\bottomrule|\\end\{tabular\})", t_body, flags=re.DOTALL)
        first_row = ""
        leads_with_small_draft = False
        if mid_m:
            rows_raw = [
                r.strip()
                for r in mid_m.group(1).splitlines()
                if "&" in r and not r.strip().startswith("%") and not r.strip().startswith("\\multicolumn")
            ]
            if rows_raw:
                first_row = rows_raw[0].split("\\\\")[0].strip()[:100]
                # Check if first cell starts with small draft like `0.5B \to` or `0.6B \to` or `1.5B \to`
                first_cell = first_row.split("&")[0].strip()
                if re.search(r"^(?:Qwen\d*(?:\.\d+)?-)?(?:0\.[56]B|1\.[58]B)\s*(?:\\to|\\rightarrow|->)", first_cell):
                    leads_with_small_draft = True

        table_summaries.append(
            {
                "label": label,
                "caption": caption,
                "first_data_row": first_row,
                "leads_with_small_draft_warning": leads_with_small_draft,
            }
        )

    # Inspect figures & check for editable .pptx companions
    fig_dir = base_dir / "figures"
    pdf_figs = sorted(fig_dir.glob("*.pdf")) if fig_dir.exists() else []
    pptx_figs = sorted(fig_dir.glob("*.pptx")) if fig_dir.exists() else []

    small_draft_warnings = [t for t in table_summaries if t["leads_with_small_draft_warning"]]
    abstract_concise_ok = w_count <= 250

    result = {
        "status": "PASS" if (abstract_concise_ok and len(small_draft_warnings) == 0) else "WARN",
        "abstract": {
            "word_count": w_count,
            "target_range": [150, 220],
            "long_parentheticals_count": paren_count,
            "concise_ok": abstract_concise_ok,
        },
        "tables": {
            "total_tables_inspected": len(table_summaries),
            "small_draft_first_warnings": len(small_draft_warnings),
            "details": table_summaries,
        },
        "figures": {
            "figures_dir": str(fig_dir),
            "pdf_figures": [p.name for p in pdf_figs],
            "pptx_editable_figures": [p.name for p in pptx_figs],
        },
    }

    if args.output:
        out_path = Path(args.output).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[{result['status']}] De-Bloating & Readability Check:")
    print(f"  - Abstract word count: {w_count} words (target 150-220, long parentheticals: {paren_count}) -> {'OK' if abstract_concise_ok else 'BLOATED'}")
    print(f"  - Tables inspected: {len(table_summaries)} (small-draft-first warnings: {len(small_draft_warnings)})")
    print(f"  - Figure assets in {fig_dir.name}/: {len(pdf_figs)} PDF(s), {len(pptx_figs)} editable PPTX(s)")
    if args.output:
        print(f"Saved JSON debloat report to: {args.output}")
    return 0 if result["status"] == "PASS" else 2


def cmd_status(args: argparse.Namespace) -> int:
    evolve_dir = Path(args.evolve_dir).resolve()
    ledger_path = evolve_dir / "review_ledger.json"
    if not ledger_path.exists():
        print(f"No ledger found at {ledger_path}.", file=sys.stderr)
        return 1
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    conv = evaluate_convergence(ledger)
    print(f"Venue: {ledger.get('venue_display_name')} | Rounds completed: {len(ledger.get('rounds', []))}")
    print(f"Converged: {conv['converged']} | {conv['reason']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Top-Venue Blind Review & Self-Evolution CLI (`paper-review-evolve`)")
    sub = p.add_subparsers(dest="cmd", required=True)

    # init
    p_init = sub.add_parser("init", help="Initialize review_ledger.json")
    p_init.add_argument("--project-dir", default=".", help="Paper project root directory")
    p_init.add_argument("--evolve-dir", default=".scratch/paper-review-evolve", help="Directory to store review ledger & prompts")
    p_init.add_argument("--venue", default="sp", choices=list(VENUE_DEFAULTS.keys()), help="Target top venue profile")
    p_init.add_argument("--tex", default="", help="Path to main.tex")
    p_init.add_argument("--pdf", default="", help="Path to compiled main.pdf")
    p_init.add_argument("--accept-threshold", type=float, default=None, help="Override accept score threshold")
    p_init.add_argument("--max-body-pages", type=int, default=None, help="Override max body pages")
    p_init.add_argument("--max-total-pages", type=int, default=None, help="Override max total pages")
    p_init.add_argument("--exemplar", action="append", default=[], help="Recent venue exemplar paper title/citation")
    p_init.add_argument("--forbid-pattern", action="append", default=[], help="Regex pattern forbidden in manuscript")
    p_init.set_defaults(func=cmd_init)

    # prompts
    p_prompts = sub.add_parser("prompts", help="Generate 3 orthogonal zero-context blind review prompts")
    p_prompts.add_argument("--evolve-dir", default=".scratch/paper-review-evolve", help="Directory containing review_ledger.json")
    p_prompts.add_argument("--round", type=int, default=None, help="Review round number (defaults to next round)")
    p_prompts.add_argument("--tex", default=None, help="Override path to main.tex")
    p_prompts.add_argument("--pdf", default=None, help="Override path to main.pdf")
    p_prompts.set_defaults(func=cmd_prompts)

    # record
    p_rec = sub.add_parser("record", help="Record Round k reviewer scores & Major/Minor counts")
    p_rec.add_argument("--evolve-dir", default=".scratch/paper-review-evolve", help="Directory containing review_ledger.json")
    p_rec.add_argument("--round", type=int, required=True, help="Round number")
    p_rec.add_argument("--scores", type=float, nargs=3, required=True, help="3 scores for R1, R2, R3")
    p_rec.add_argument("--majors", type=int, nargs=3, default=[0, 0, 0], help="Major weakness counts for R1, R2, R3")
    p_rec.add_argument("--minors", type=int, nargs=3, default=[0, 0, 0], help="Minor weakness counts for R1, R2, R3")
    p_rec.add_argument("--summary", default="", help="Concise summary of fixes completed in this round")
    p_rec.set_defaults(func=cmd_record)

    # audit
    p_audit = sub.add_parser("audit", help="Run deterministic manuscript, log, and PDF anonymity checks")
    p_audit.add_argument("--tex", required=True, help="Path to main.tex")
    p_audit.add_argument("--pdf", default=None, help="Path to compiled main.pdf")
    p_audit.add_argument("--log", default=None, help="Path to LaTeX .log file")
    p_audit.add_argument("--venue", default="sp", choices=list(VENUE_DEFAULTS.keys()), help="Target venue profile")
    p_audit.add_argument("--max-abstract-words", type=int, default=None, help="Override max abstract words")
    p_audit.add_argument("--max-body-pages", type=int, default=None, help="Override max body pages")
    p_audit.add_argument("--max-total-pages", type=int, default=None, help="Override max total pages")
    p_audit.add_argument("--max-overfull-pt", type=float, default=None, help="Override max Overfull \\hbox pt")
    p_audit.add_argument("--forbid-pattern", action="append", default=[], help="Regex pattern forbidden in manuscript")
    p_audit.add_argument("--scrub", action="store_true", help="Scrub PDF metadata/XMP/PTEX banner in-place before checking")
    p_audit.add_argument("--output", default=None, help="Path to write JSON audit report")
    p_audit.set_defaults(func=cmd_audit)

    # debloat-check
    p_deb = sub.add_parser("debloat-check", help="Check abstract conciseness, Target-First table ordering, and figures")
    p_deb.add_argument("--tex", required=True, help="Path to main.tex")
    p_deb.add_argument("--output", default=None, help="Path to write JSON debloat report")
    p_deb.set_defaults(func=cmd_debloat_check)

    # status
    p_stat = sub.add_parser("status", help="Show current review convergence ledger status")
    p_stat.add_argument("--evolve-dir", default=".scratch/paper-review-evolve", help="Directory containing review_ledger.json")
    p_stat.set_defaults(func=cmd_status)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
