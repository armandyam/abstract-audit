#!/usr/bin/env python3
"""The TMLR paper's remaining data-driven tables, as LaTeX.

make_macros.py writes the six tables the paper generated with its macros.
This script writes the other seven tables whose contents come from the
pipeline or the code, each from the paper's own table as the template (the
same layout, labels and caption, with every number computed):

  acronym_reuse_freq.tex     aggregate/acronym_reuse_freq.csv; the caption's
                             shares from the per-paper acronym lists and
                             shared/baselines/acronym_histograms.csv
  citation_readability_top_bottom_combined.tex
                             aggregate/citations/, citations stage
  citation_llm_top_bottom_combined.tex
                             aggregate/citations/, citations stage
  corpus.tex                 tab:corpus: pgfplots/tmlr/papers_per_year.csv
                             and shared/baselines/papers_per_year.csv
  self_audit.tex             tab:self-audit: aggregate/self_audit.csv
  prompts.tex                tab:prompts: PROMPTS in src/metrics/llm_scores.py
  normalisation_rules.tex    each example run through
                             processing/text_cleaning.clean_abstract

Two tables carry no computed value and are committed as they are printed:
paper/tmlr/tables/metric_families.tex and nine.tex.

Writes under --out-dir (default $AA_DATA/tmlr/tables) and records in
$AA_DATA/tmlr/tables.json what was written and what was not, and why:

  citation   the citation outputs are absent (the counts are not
             distributed; see README, Citations)
  paper      aggregate/self_audit.csv is absent: the self-audit measures the
             paper's own abstract, which is not distributed (AA_PAPER)
  incomplete any other input is absent (the --from aggregate route has no
             processed abstracts); check_tables.py reports it as missing

    python paper/tmlr/make_tables.py
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "src"))

import claims as C  # noqa: E402

VENUE_LABEL = {"neurips": "NeurIPS", "iclr": "ICLR", "icml": "ICML"}
CITATION = ("citation_readability_top_bottom_combined.tex",
            "citation_llm_top_bottom_combined.tex")


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


# ===================================================== acronym reuse ===

REUSE_ROWS = [("NeurIPS", "NeurIPS"), ("ICLR", "ICLR"), ("ICML", "ICML"),
              ("arXiv ML", "arXiv ML"), ("arXiv non-ML", "arXiv non-ML"),
              ("PubMed", "PubMed"), ("B\\&D (2020)", "Barnett and Doubleday (2020)")]
BUCKETS = ["1", "2--9", "10--99", "100--999", "1000+"]


def acronym_reuse_freq(ctx: C.Ctx) -> str:
    df = pd.read_csv(need(os.path.join(ctx.data, "aggregate", "acronym_reuse_freq.csv")))
    df = df.set_index("venue")
    lines = []
    for key, lab in REUSE_ROWS:
        r = df.loc[key]
        bd = key.startswith("B\\&D")
        cells = []
        for b in BUCKETS:
            v = r[b]
            cells.append(r"\multicolumn{1}{c}{n/a}" if pd.isna(v) else f"{v:.1f}\\%")
        if not bd:
            cells[0] = r"\textbf{" + cells[0] + "}"
        n = thousands(r.n_unique)
        if key == "PubMed":
            # the paper marks this row as revised in round 4
            n = r"\revfour{" + n + "}"
            cells = [r"\revfour{" + c + "}" for c in cells]
        lines.append(f"{lab} & {n} & " + " & ".join(cells) + r" \\")
    for p in [os.path.join(ctx.data, "per_paper", "acronyms", f"{v}.csv") for v in C.CONFS]:
        need(p)
    lo, hi = C.reuse_share_range(ctx)
    pubmed = C.reuse_share(ctx, "pubmed")
    return (r"""\begin{table}[t]
\centering
\scriptsize
\begin{tabular}{lrrrrrr}
\toprule
Venue & Unique acronyms & 1 & 2--9 & 10--99 & 100--999 & 1000+ \\
\midrule
""" + "\n".join(lines) + r"""
\bottomrule
\end{tabular}
\caption{Acronym frequency distribution by venue (abstract acronyms). Each cell shows the percentage of unique acronyms appearing in that frequency range. The external baseline is Barnett and Doubleday (2020), PubMed titles and abstracts, 1950--2019. Single-use rates are comparable across venues. ML venues carry a larger 2--9 use bucket. Roughly """
            + f"{lo:.0f} to {hi:.0f} percent of ML acronyms appear fewer than ten times against "
            + f"{pubmed:.0f}" + r""" percent in PubMed. A value of n/a means that the source does not report the frequency range.}
\label{tab:acronym-reuse}
\end{table}
""")


# ========================================================= citations ===

READABILITY_ROWS = [
    ("flesch_ease", "Flesch Reading Ease", "↑ better"),
    ("flesch_kincaid", "Flesch–Kincaid Grade", "↓ better"),
    ("gunning_fog", "Gunning Fog Index", "↓ better"),
    ("smog", "SMOG Index", "↓ better"),
    ("dale_chall", "Dale–Chall Score", "↓ better"),
    ("spache", "Spache Grade", "↓ better"),
    ("coleman_liau", "Coleman–Liau Index", "↓ better"),
    ("ari", "ARI", "↓ better"),
    ("linsear_write", "Linsear Write", "↓ better"),
    ("lix", "LIX", "↓ better"),
    ("rix", "RIX", "↓ better"),
    ("forcast", "FORCAST", "↓ better"),
    ("powers_sumner_kearl", "Powers–Sumner–Kearl Grade", "↓ better"),
    ("avg_sentence_length", "Words per sentence", "↓ better"),
    ("avg_syllables_per_word", "Syllables per word", "↓ better"),
]
BOLD_MIN = 0.05     # the caption's threshold for a gap worth emphasising


def _signed(x: float) -> str:
    return ("+" if x > 0 else "") + f"{x:.2f}"


def citation_readability(ctx: C.Ctx) -> str:
    path = need(os.path.join(ctx.cit_dir, "citation_readability_top_bottom_combined.csv"),
                "citation")
    df = pd.read_csv(path).set_index("metric")
    lines = []
    for key, lab, direction in READABILITY_ROWS:
        r = df.loc[key]
        d = _signed(r.delta)
        favours = (r.delta > 0) if direction.startswith("↑") else (r.delta < 0)
        if favours and abs(r.delta) >= BOLD_MIN:
            d = r"\textbf{" + d + "}"
        lines.append(f"{lab} & {direction} & {r.top_mean:.2f} $\\pm$ {r.top_ci:.2f} & "
                     f"{r.bottom_mean:.2f} $\\pm$ {r.bottom_ci:.2f} & {d} \\\\")
    top_n, bottom_n = int(df.top_n.iloc[0]), int(df.bottom_n.iloc[0])
    year = C.cit_max_year(ctx)
    return (r"""\begin{table}[t]
\centering
\small
\begin{tabular}{llccc}
\toprule
Metric & Better & Top 10\% & Bottom 10\% & $\Delta$ (top $-$ bottom) \\
\midrule
""" + "\n".join(lines) + r"""
\midrule
\multicolumn{5}{l}{\small $n_\text{top}=""" + thousands(top_n) + r"""$, $n_\text{bottom}=""" + thousands(bottom_n) + r"""$ papers.} \\
\bottomrule
\end{tabular}
\caption{NeurIPS, ICLR, and ICML readability for top-10 percent vs bottom-10 percent cited papers (within-year citation percentile, pooled through """ + str(year) + r"""). The most recent year is excluded because its citation counts are immature. Values are mean with 95 percent confidence interval (normal approximation). Bold indicates the gap favours the top-cited group by at least """ + f"{BOLD_MIN}" + r""" in magnitude.}
\label{tab:citation-readability-combined}
\end{table}
""")


PROMPT_LABEL = {"simple": "Simple", "ascb": "ASCB", "own_reasoning": "Own reasoning"}


def citation_llm(ctx: C.Ctx) -> str:
    path = need(os.path.join(ctx.cit_dir, "citation_llm_top_bottom_combined.csv"), "citation")
    df = pd.read_csv(path)
    lines = []
    for i, (prompt, g) in enumerate(df.groupby("prompt", sort=False)):
        if i:
            lines.append(r"\midrule")
        lines.append(r"\multicolumn{5}{l}{\textbf{" + PROMPT_LABEL[prompt] + r"}} \\")
        for r in g.itertuples():
            d = _signed(r.delta)
            if r.delta > 0:
                d = r"\textbf{" + d + "}"
            lines.append(f" & {VENUE_LABEL[r.venue]} & {r.top_mean:.2f} $\\pm$ {r.top_ci:.2f} & "
                         f"{r.bottom_mean:.2f} $\\pm$ {r.bottom_ci:.2f} & {d} \\\\")
    n_models = int(df.n_models.max())
    words = {6: "six"}
    year = C.cit_max_year(ctx)
    return (r"""\begin{table}[t]
\centering
\small
\begin{tabular}{llccc}
\toprule
Prompt & Venue & Top 10\% & Bottom 10\% & $\Delta$ \\
\midrule
""" + "\n".join(lines) + r"""
\bottomrule
\end{tabular}
\caption{LLM-as-judge readability for top-10\% vs bottom-10\% cited papers across NeurIPS, ICLR, and ICML (within-venue-year percentile, pooled through """ + str(year) + r"""). Each cell is the mean across the """ + words.get(n_models, str(n_models)) + r""" models of that model's group-mean score (1--5, higher = easier), with a 95\% CI over the """ + words.get(n_models, str(n_models)) + r""" model means. $\Delta$ = top $-$ bottom. Bold where top-cited papers are rated easier.}
\label{tab:citation-llm}
\end{table}
""")


# ============================================================ corpus ===

def corpus(ctx: C.Ctx) -> str:
    need(os.path.join(ctx.data, "tmlr", "pgfplots", "papers_per_year.csv"))
    rows = [("arXiv (all categories)", "arxiv"), ("NeurIPS", "neurips"),
            ("ICLR", "iclr"), ("ICML", "icml"), ("PubMed", "pubmed")]
    lines = []
    for lab, g in rows:
        a, b = C.corpus_years(ctx, g)
        lines.append(f"    {lab:<22} & {f'{a}--{b}':<11} & "
                     f"{thousands(C.corpus_size(ctx, g), '{,}')} \\\\")
    ahead = C.pubmed_ahead_of_print(ctx)
    y0, y1 = C.pubmed_ahead_years(ctx, "min"), C.pubmed_ahead_years(ctx, "max")
    return (r"""\begin{table}[h]
  \centering
  \begin{tabular}{llr}
    \toprule
    Source                 & Coverage    & Papers \\
    \midrule
""" + "\n".join(lines) + r"""
    \bottomrule
  \end{tabular}
  \caption{Per source paper counts and coverage at the 2026-04
  snapshot. The arXiv 2025 row covers approximately three
  quarters of the calendar year. The NLM baseline additionally
  carries """ + thousands(ahead) + f""" ahead-of-print PubMed records dated {y0} and
  {y1}""" + r""". An ahead-of-print date is not a publication year, so these
  are excluded from the PubMed count above and from every
  year-indexed analysis and figure\revfour{, and from the pooled
  acronym reuse distribution of Table~\ref{tab:acronym-reuse}}.}
  \label{tab:corpus}
\end{table}
""")


# ======================================================== self-audit ===

# The table's labels for the metric names audit_self.py writes.
AUDIT_LABEL = {"Flesch-Kincaid Grade": "Flesch--Kincaid Grade", "Dale-Chall": "Dale--Chall",
               "Coleman-Liau": "Coleman--Liau", "Powers-Sumner-Kearl": "Powers--Sumner--Kearl",
               "Type-token ratio": "Type--token ratio", "Additional": "Additional emphasis"}
# The authors' judgment against their approved-term list, which audit_self.py
# does not compute (it prints the acronyms it finds); kept as printed.
NOVEL_ACRONYM_ROWS = [("Novel acronyms (title)", "0", "n/a"),
                      ("Novel acronyms (abstract)", "0", "n/a")]


def self_audit(ctx: C.Ctx) -> str:
    df = pd.read_csv(need(os.path.join(ctx.data, "aggregate", "self_audit.csv"), "paper"))

    def row(r) -> str:
        lab = AUDIT_LABEL.get(r.metric, r.metric)
        return f"    {lab:<25} & {r.abstract:.2f}   & {r.percentile:.1f}\\% \\\\"

    def block(title: str, fam: str) -> list[str]:
        g = df[df.family == fam]
        return [r"    \multicolumn{3}{l}{\textbf{" + f"{title} ({len(g)})" + r"}} \\",
                r"    \midrule"] + [row(r) for r in g.itertuples()]

    def head() -> list[str]:
        return [r"  \begin{tabular}{lrr}", r"    \toprule", r"    Metric & A & Pct \\",
                r"    \midrule"]

    left = head() + block("Classical readability", "readability") + [
        r"    \midrule", r"    \multicolumn{3}{l}{\textbf{Acronyms}} \\", r"    \midrule"]
    left += [row(r) for r in df[df.family == "acronyms"].itertuples()]
    left += [f"    {a:<25} & {b}     & {c} \\\\" for a, b, c in NOVEL_ACRONYM_ROWS]
    left += [r"    \bottomrule", r"  \end{tabular}"]
    right = head() + block("Writing style suite", "style") + [r"    \midrule"]
    right += block("Sensational language", "sensational")
    right += [r"    \bottomrule", r"  \end{tabular}"]
    pp = ctx.per_paper("readability", "neurips")
    n = len(pp)
    y0, y1 = int(pp.year.min()), int(pp.year.max())
    return (r"""\begin{table}[t]
  \centering
  \scriptsize
  \begin{minipage}[t]{0.48\linewidth}
  \centering
""" + "\n".join(left) + r"""
  \end{minipage}\hfill
  \begin{minipage}[t]{0.48\linewidth}
  \centering
""" + "\n".join(right) + r"""
  \end{minipage}
  \caption{Metric self-audit of this manuscript. Numbers are
  produced by running the same per-paper metric scripts used
  throughout the paper on this paper's own title and abstract.
  Percentile refers to the NeurIPS """ + f"{y0}--{y1}" + r""" abstract
  distribution for the same metric (n=""" + thousands(n) + r"""). Hohmann-suite and
  sensational-language metrics are computed at the abstract level
  only. The title falls below the readability scripts' minimum
  word count, so its classical scores are not reported. A percentile is not
  defined for a count of novel acronyms, which is shown as n/a. A = abstract,
  Pct = percentile.}
  \label{tab:self-audit}
\end{table}
""")


# =========================================================== prompts ===

PROMPT_TITLE = {"simple": "Simple Prompt", "ascb": "ASCB Guidelines Prompt",
                "own_reasoning": "Own Reasoning Prompt"}


def prompt_tex(text: str) -> str:
    """A prompt template as the paper typesets it: each newline shown as a
    literal \\n and broken there, list dashes as en dashes, the placeholders
    in typewriter."""
    def seg(s: str) -> str:
        s = s.replace("<score>", r"\texttt{<score>}")
        s = s.replace("{SUMMARY}", r"\texttt{\{SUMMARY\}}")
        return re.sub(r"^- ", r"{\\textendash} ", s)
    parts = re.split(r" ?(\n\n|\n)", text)
    out = [seg(parts[0])]
    for sep, s in zip(parts[1::2], parts[2::2]):
        mark = r"\textbackslash n \textbackslash n" if sep == "\n\n" else r"\textbackslash n"
        out.append(r" \texttt{" + mark + r"} \newline" + "\n" + seg(s))
    return "".join(out)


def prompts(ctx: C.Ctx) -> str:
    from metrics.llm_scores import PROMPTS
    blocks = []
    for name, text in PROMPTS.items():
        blocks.append(r"\textbf{" + PROMPT_TITLE[name] + r"} \\" + "\n\\midrule\n"
                      + prompt_tex(text) + r" \\")
    return (r"""\begin{table}[h]
\centering
\small
\begin{tabular}{@{}p{\dimexpr\linewidth-2\tabcolsep\relax}@{}}
\toprule
""" + "\n\\midrule\n".join(blocks) + r"""
\bottomrule
\end{tabular}
\caption{The three prompt templates we apply, reproduced
verbatim from \citet{cachola2025evaluating} (Table~10) except
that the \texttt{Reason:~<reasoning>} output line is omitted.
\texttt{\{SUMMARY\}} is replaced by the abstract text at
inference.}
\label{tab:prompts}
\end{table}
""")


# =============================================================== normalisation rules ===

SOFT = "\u00ad"     # where the typeset example may break; removed before cleaning
RULE_EXAMPLES = [
    ("Inline mathematics", r"coresets ($\texttt{FWC}$)"),
    ("Display mathematics", r"regret is $O(\sqrt{T})$"),
    ("Mathematics spliced inside a word", r"$\underline{Co}$llabo" + SOFT + r"$\underline{ra}$tive"),
    ("Text-mode commands", r"the \emph{\textbf{same}} setting"),
    ("URLs", "available at https://" + SOFT + "github.com/ex/repo"),
    ("Identifiers", "see arXiv:2401.00001"),
    ("Ampersands", "speed & accuracy"),
    ("Non-ASCII characters", "the café corpus"),
    ("Section headings", "OBJECTIVE: We study scaling."),
]


def tt(s: str) -> str:
    """Text for \\texttt: every character LaTeX would interpret, escaped."""
    s = s.replace("\\", "\x00")
    for a, b in [("{", r"\{"), ("}", r"\}"), ("$", r"\$"), ("&", r"\&"),
                 ("é", r"\'e"), (SOFT, r"\-"), ("\x00", r"\textbackslash ")]:
        s = s.replace(a, b)
    return r"\texttt{" + s + "}"


def normalisation_rules(ctx: C.Ctx) -> str:
    from processing.text_cleaning import clean_abstract
    rows = []
    for lab, raw in RULE_EXAMPLES:
        after = clean_abstract(raw.replace(SOFT, ""))
        rows.append(f"    {lab}\n      & {tt(raw)}\n      & {tt(after)} \\\\")
    return (r"""\begin{table}[h]
  \centering
  \small
  \begin{tabular}{p{0.24\textwidth}p{0.36\textwidth}p{0.28\textwidth}}
    \toprule
    Element & Before & After \\
    \midrule
""" + "\n    \\addlinespace\n".join(rows) + r"""
    \bottomrule
  \end{tabular}
\caption{\revtwo{Text normalisation rules, with the effect of each on a
  worked example. Applied for the sensitivity analysis in
  Table~\ref{tab:normalisation}. The reported metrics are computed on the
  abstract as published.}}
  \label{tab:normalisation-rules}
\end{table}
""")


# ============================================================== output ===

TABLES = {
    "acronym_reuse_freq.tex": acronym_reuse_freq,
    "citation_readability_top_bottom_combined.tex": citation_readability,
    "citation_llm_top_bottom_combined.tex": citation_llm,
    "corpus.tex": corpus,
    "self_audit.tex": self_audit,
    "prompts.tex": prompts,
    "normalisation_rules.tex": normalisation_rules,
}
REASONS = {"citation": "citation outputs absent from aggregate/citations/",
           "paper": "aggregate/self_audit.csv absent: the self-audit needs the "
                    "manuscript (AA_PAPER), which is not distributed"}


def build(data_dir: str, out_dir: str) -> dict:
    """Write every table it can; return the tables.json record."""
    os.makedirs(out_dir, exist_ok=True)
    ctx = C.Ctx(data_dir, "strict")
    rec: dict = {"written": [], "skipped": {}, "incomplete": {}}
    for name, fn in TABLES.items():
        path = os.path.join(out_dir, name)
        try:
            tex = fn(ctx)
        except Absent as e:
            if os.path.exists(path):
                os.remove(path)          # never leave a table from an earlier run
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
    ap.add_argument("--out-dir", default=None, help="default: {data-dir}/tmlr/tables")
    a = ap.parse_args()
    out = a.out_dir or os.path.join(a.data_dir, "tmlr", "tables")
    rec = build(a.data_dir, out)
    print(f"  tables: {len(rec['written'])} written to {out}")
    for name, why in rec["skipped"].items():
        print(f"  skipped {name}: {why}")
    for name, what in rec["incomplete"].items():
        print(f"  INCOMPLETE {name}: input absent {what}")


if __name__ == "__main__":
    main()
