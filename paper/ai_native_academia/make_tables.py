#!/usr/bin/env python3
"""The AI-Native Academia paper's other data-driven tables, as LaTeX.

make_macros.py writes the topic profile table with the macros. This script
writes the paper's four other generated tables, each with the paper's
layout and every cell computed:

  acronym_reuse_freq.tex     aggregate/acronym_reuse_freq.csv (analysis
                             stage, src/analysis/acronym_reuse.py): the
                             NeurIPS, arXiv ML, arXiv non-ML, PubMed and
                             Barnett and Doubleday rows
  judge_raw_stability.tex    aggregate/judge_raw_levels_neurips.csv and
                             judge_run_stability_neurips.csv
                             (src/analysis/judge_agreement.py)
  judge_agreement.tex        aggregate/judge_pairwise_agreement_neurips.csv
                             and judge_cronbach_alpha_neurips.csv (the same)
  citation_readability_top_bottom.tex
                             aggregate/citations/citation_readability_top_bottom.csv
                             (src/citations/readability_deciles.py --venues
                             neurips), citations stage

The tables carry no caption: the captions are manuscript text, which is not
distributed. The numbers the captions print are computed here all the same
and recorded in tables.json under "caption_values" (table: {name: printed
form}); check_tables.py looks each one up in the paper's caption when the
manuscript is given.

Writes under --out-dir (default $AA_DATA/ai_native_academia/tables) and
records in tables.json, in that directory's parent, what was written and what
was not, and why:

  citation   the citation outputs are absent (the counts are not
             distributed; see README, Citations)
  incomplete any other input is absent; check_tables.py reports the table
             as missing

    python paper/ai_native_academia/make_tables.py
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "src"))


def _claims():
    """paper/tmlr/claims.py, for the acronym reuse shares it already computes."""
    if "claims" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "claims", os.path.join(REPO, "paper", "tmlr", "claims.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules["claims"] = mod
        spec.loader.exec_module(mod)
    return sys.modules["claims"]


VENUE = "neurips"
CITATION = ("citation_readability_top_bottom.tex",)


def thousands(n: float, sep: str = ",") -> str:
    return f"{int(round(n)):,}".replace(",", sep)


class Absent(FileNotFoundError):
    """A table's input is absent; `kind` says which exemption applies."""

    def __init__(self, path: str, kind: str):
        super().__init__(path)
        self.path, self.kind = path, kind


def need(path: str, kind: str = "incomplete") -> str:
    if not os.path.exists(path):
        raise Absent(path, kind)
    return path


def table(spec: str, header: str, rows: list[str], label: str,
          size: str = "\\small", extra: str = "") -> str:
    return ("\\begin{table}[t]\n\\centering\n" + size + "\n"
            f"\\begin{{tabular}}{{{spec}}}\n\\toprule\n{header} \\\\\n\\midrule\n"
            + "\n".join(rows) + "\n" + extra
            + "\\bottomrule\n\\end{tabular}\n"
            f"\\label{{{label}}}\n\\end{{table}}\n")


# ===================================================== acronym reuse ===

REUSE_ROWS = ["NeurIPS", "arXiv ML", "arXiv non-ML", "PubMed", "B\\&D (2020)"]
BUCKETS = ["1", "2--9", "10--99", "100--999", "1000+"]


def acronym_reuse_freq(data: str, captions: dict) -> str:
    df = pd.read_csv(need(os.path.join(data, "aggregate", "acronym_reuse_freq.csv")))
    df = df.set_index("venue")
    lines = []
    for key in REUSE_ROWS:
        r = df.loc[key]
        bd = key.startswith("B\\&D")
        cells = ["---" if pd.isna(r[b]) else f"{r[b]:.1f}\\%" for b in BUCKETS]
        if not bd:
            cells[0] = "\\textbf{" + cells[0] + "}"
        lines.append(f"{key} & {thousands(r.n_unique)} & " + " & ".join(cells) + " \\\\")
    # The caption: the share of ML acronyms used fewer than ten times
    # (NeurIPS and arXiv ML), against the science-wide baseline.
    for v in ("iclr", "icml"):           # claims.py counts every conference
        need(os.path.join(data, "per_paper", "acronyms", f"{v}.csv"))
    C = _claims()
    ctx = C.Ctx(data)
    lo, hi = C.reuse_share_range(ctx, "neurips+arxiv_ml")
    captions["acronym_reuse_freq.tex"] = {
        "ml_fewer_than_ten_min": f"{lo:.0f}", "ml_fewer_than_ten_max": f"{hi:.0f}",
        "science_wide_fewer_than_ten": f"{C.reuse_share(ctx, 'bd'):.0f}"}
    return table("lrrrrrr", "Venue & Unique acronyms & 1 & 2--9 & 10--99 & 100--999 & 1000+",
                 lines, "tab:acronym-reuse")


# ============================================================ judges ===

SHORT = {
    "Gemma-3-27B-Instruct": "Gemma-3-27B",
    "Gemma-4-31B-Instruct": "Gemma-4-31B",
    "Llama-3.1-8B-Instruct": "Llama-3.1-8B",
    "Mistral-7B-Instruct": "Mistral-7B",
    "Mixtral-8x7B-Instruct": "Mixtral-8x7B",
    "Qwen2.5-32B-Instruct": "Qwen2.5-32B",
}
PROMPT_LABEL = {"simple": "\\texttt{simple}", "ascb": "\\texttt{ascb}",
                "own_reasoning": "\\texttt{own\\_reasoning}"}
STABILITY_PROMPT = "simple"     # the raw-stability table reports one prompt


def judge_raw_stability(data: str, captions: dict) -> str:
    agg = os.path.join(data, "aggregate")
    st = pd.read_csv(need(os.path.join(agg, f"judge_run_stability_{VENUE}.csv")))
    rw = pd.read_csv(need(os.path.join(agg, f"judge_raw_levels_{VENUE}.csv")))
    n = pd.read_csv(need(os.path.join(agg, f"judge_scored_papers_{VENUE}.csv")))
    first, last = sorted(int(c[4:]) for c in rw.columns
                         if c.startswith("raw_") and c[4:].isdigit())
    st = st[st.prompt_name == STABILITY_PROMPT].set_index("model")
    rw = rw[rw.prompt_name == STABILITY_PROMPT].set_index("model")
    n = n[n.prompt_name == STABILITY_PROMPT]
    lines = [f"{short} & {rw.loc[m, f'raw_{first}']:.2f} & {rw.loc[m, f'raw_{last}']:.2f} & "
             f"{rw.loc[m, 'raw_delta']:+.2f} & {st.loc[m, 'mean_run_sd']:.2f} & "
             f"{st.loc[m, 'pct_all_three_identical']:.0f}\\% \\\\"
             for m, short in SHORT.items()]
    captions["judge_raw_stability.tex"] = {
        "first_year_papers_min": str(int(n[f"n_{first}"].min())),
        "first_year_papers_max": str(int(n[f"n_{first}"].max())),
        "last_year_papers": thousands(n[f"n_{last}"].max()),
    }
    return table("lrrrrr", f"Model & {first} & {last} & $\\Delta$ & SD & Same",
                 lines, "tab:raw-stability", size="\\small")


def judge_agreement(data: str, captions: dict) -> str:
    agg = os.path.join(data, "aggregate")
    pa = pd.read_csv(need(os.path.join(agg, f"judge_pairwise_agreement_{VENUE}.csv")))
    al = pd.read_csv(need(os.path.join(agg, f"judge_cronbach_alpha_{VENUE}.csv")))
    al = al.set_index("prompt")
    lines = []
    for prompt, lab in PROMPT_LABEL.items():
        rho = pa[pa.prompt == prompt]["spearman"]
        lines.append(f"{lab} & {rho.mean():.3f} & {rho.min():.3f} & {rho.max():.3f} & "
                     f"{al.loc[prompt, 'cronbach_alpha']:.3f} \\\\")
    captions["judge_agreement.tex"] = {
        "model_pairs": str(int(pa.groupby("prompt").size().max())),
        "papers_min": thousands(al.n_papers.min(), "{,}"),
        "papers_max": thousands(al.n_papers.max(), "{,}"),
    }
    return table("lrrrr", "Prompt & mean $\\rho$ & min & max & $\\alpha$",
                 lines, "tab:agreement")


# ========================================================= citations ===

READABILITY_ROWS = [
    ("flesch_ease", "Flesch Reading Ease", "↑ better"),
    ("flesch_kincaid", "Flesch-Kincaid Grade", "↓ better"),
    ("gunning_fog", "Gunning Fog Index", "↓ better"),
    ("smog", "SMOG Index", "↓ better"),
    ("dale_chall", "Dale-Chall Score", "↓ better"),
    ("spache", "Spache Grade", "↓ better"),
    ("coleman_liau", "Coleman-Liau Index", "↓ better"),
    ("ari", "ARI", "↓ better"),
    ("linsear_write", "Linsear Write", "↓ better"),
    ("lix", "LIX", "↓ better"),
    ("rix", "RIX", "↓ better"),
    ("forcast", "FORCAST", "↓ better"),
    ("powers_sumner_kearl", "Powers-Sumner-Kearl Grade", "↓ better"),
    ("avg_sentence_length", "Words per sentence", "↓ better"),
    ("avg_syllables_per_word", "Syllables per word", "↓ better"),
]
BOLD_MIN = 0.05     # a gap of at least this size favouring the top group is bold
MAX_YEAR = 2024     # readability_deciles.py --max-year


def _signed(x: float) -> str:
    return ("+" if x > 0 else "") + f"{x:.2f}"


def citation_readability(data: str, captions: dict) -> str:
    """Gated on the citations stage's CSV, but computed again from the
    per-paper files: that CSV holds four decimals, and the SMOG gap
    (-0.47507) prints as -0.48 only at full precision."""
    need(os.path.join(data, "aggregate", "citations",
                      "citation_readability_top_bottom.csv"), "citation")
    from citations.readability_deciles import load, top_bottom
    df = top_bottom(load([VENUE], MAX_YEAR,
                         read_dir=os.path.join(data, "per_paper", "readability"),
                         cit_dir=os.path.join(data, "per_paper", "citations")))
    df = df.set_index("metric")
    lines = []
    for key, lab, direction in READABILITY_ROWS:
        r = df.loc[key]
        d = _signed(r.delta)
        favours = (r.delta > 0) if direction.startswith("↑") else (r.delta < 0)
        if favours and abs(r.delta) >= BOLD_MIN:
            d = "\\textbf{" + d + "}"
        lines.append(f"{lab} & {direction} & {r.top_mean:.2f} $\\pm$ {r.top_ci:.2f} & "
                     f"{r.bottom_mean:.2f} $\\pm$ {r.bottom_ci:.2f} & {d} \\\\")
    top_n, bottom_n = int(df.top_n.iloc[0]), int(df.bottom_n.iloc[0])
    captions["citation_readability_top_bottom.tex"] = {
        "pooled_through": str(MAX_YEAR), "bold_threshold": f"{BOLD_MIN}"}
    extra = ("\\midrule\n\\multicolumn{5}{l}{\\small $n_\\text{top}=" + thousands(top_n)
             + "$, $n_\\text{bottom}=" + thousands(bottom_n) + "$ papers.} \\\\\n")
    return table("llccc",
                 "Metric & Better & Top 10\\% & Bottom 10\\% & $\\Delta$ (top $-$ bottom)",
                 lines, "tab:citation-readability", extra=extra)


# ============================================================== output ===

TABLES = {
    "acronym_reuse_freq.tex": acronym_reuse_freq,
    "judge_raw_stability.tex": judge_raw_stability,
    "judge_agreement.tex": judge_agreement,
    "citation_readability_top_bottom.tex": citation_readability,
}
REASONS = {"citation": "citation outputs absent from aggregate/citations/"}


def build(data_dir: str, out_dir: str) -> dict:
    """Write every table it can; return the tables.json record."""
    os.makedirs(out_dir, exist_ok=True)
    rec: dict = {"written": [], "skipped": {}, "incomplete": {}, "caption_values": {}}
    for name, fn in TABLES.items():
        path = os.path.join(out_dir, name)
        try:
            tex = fn(data_dir, rec["caption_values"])
        except Absent as e:
            if os.path.exists(path):
                os.remove(path)          # never leave a table from an earlier run
            rec["caption_values"].pop(name, None)
            if e.kind == "incomplete":
                rec["incomplete"][name] = os.path.relpath(e.path, data_dir)
            else:
                rec["skipped"][name] = REASONS[e.kind]
            continue
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(tex)
        rec["written"].append(name)
    with open(os.path.join(os.path.dirname(out_dir.rstrip(os.sep)), "tables.json"), "w") as fh:
        json.dump(rec, fh, indent=2)
        fh.write("\n")
    return rec


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default=os.environ.get("AA_DATA", "data"),
                    help="data root (default: $AA_DATA, else data)")
    ap.add_argument("--out-dir", default=None,
                    help="default: {data-dir}/ai_native_academia/tables")
    a = ap.parse_args()
    out = a.out_dir or os.path.join(a.data_dir, "ai_native_academia", "tables")
    rec = build(a.data_dir, out)
    print(f"  tables: {len(rec['written'])} written to {out}")
    for name, why in rec["skipped"].items():
        print(f"  skipped {name}: {why}")
    for name, what in rec["incomplete"].items():
        print(f"  INCOMPLETE {name}: input absent {what}")


if __name__ == "__main__":
    main()
