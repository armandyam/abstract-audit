"""
Shared preprocessing and word lists for narrator-style writing metrics.

Based on Hohmann, Barnett, King & Connell (2025), Scientometrics 130:3349-3366.
DOI: https://doi.org/10.1007/s11192-025-05353-8
Source R code: https://github.com/agbarnett/narrator

Preprocessing follows 99_main_function_abstract.R.
Word lists follow 99_key_characters_words_phrases.R.
"""

from __future__ import annotations
import json
import os
import re
import sys
from typing import Iterator

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from schema import load_processed

# ── Structured-abstract heading removal ───────────────────────────────────────
# From 99_key_characters_words_phrases.R bogus.acronyms.abstract list
# (ML papers rarely have these, but we remove them for consistency with B&D)
_HEADINGS = [
    r'BACKGROUND:', r'INTRODUCTION:', r'OBJECTIVE:', r'OBJECTIVES:',
    r'METHODS?:', r'MATERIAL AND METHODS:', r'MATERIALS AND METHODS:',
    r'RESULTS?:', r'DISCUSSION:', r'CONCLUSIONS?:', r'SUMMARY:', r'AIM:',
    r'AIMS?:', r'DESIGN:', r'SETTING:', r'SUBJECTS:', r'PARTICIPANTS:',
    r'SIGNIFICANCE:', r'IMPORTANCE:', r'PERSPECTIVE:', r'LIMITATIONS:',
    r'RECOMMENDATIONS?:', r'HYPOTHESIS:', r'PURPOSE:',
    r'KEYWORDS?:', r'KEY WORDS?:',
]
_HEADING_PAT = re.compile('|'.join(_HEADINGS), re.IGNORECASE)

# The bare ABSTRACT heading (no colon) needs its own case-SENSITIVE,
# word-bounded pattern: inside the IGNORECASE list above it matched the
# substring "abstract" anywhere, mangling ordinary words ("abstraction" ->
# "ion", "abstracts" -> "s"). Only an ALL-CAPS standalone ABSTRACT token, or
# a mixed-case "Abstract:" label at the very start, is a heading.
_ABSTRACT_HEADING_PAT = re.compile(r'\bABSTRACT\b:?')
_ABSTRACT_LABEL_PAT   = re.compile(r'^\s*Abstract\s*[:.]', re.IGNORECASE)

# ── Preprocessing ─────────────────────────────────────────────────────────────

def preprocess(text: str) -> str:
    """
    Light preprocessing of abstracts as per narrator 99_main_function_abstract.R:
    - Remove structured sub-headings
    - Expand common symbols to words
    - Normalise whitespace and bracket spacing
    """
    text = _HEADING_PAT.sub(' ', text)
    text = _ABSTRACT_HEADING_PAT.sub(' ', text)
    text = _ABSTRACT_LABEL_PAT.sub(' ', text)
    text = re.sub(r' = ',    ' equal to ',       text)
    text = re.sub(r' < ',    ' less than ',       text)
    text = re.sub(r'&lt;',   ' less than ',       text)
    text = re.sub(r' > ',    ' greater than ',    text)
    text = re.sub(r'&gt;',   ' greater than ',    text)
    text = re.sub(r' & ',    ' and ',             text)
    text = re.sub(r'&amp;',  ' and ',             text)
    text = re.sub(r'\s*[±]\s*|\s*\+/-+\s*', ' plus or minus ', text)
    text = re.sub(r'\(\s+',  '(',                 text)
    text = re.sub(r'\s+\)',  ')',                  text)
    text = re.sub(r'\s+',    ' ',                 text).strip()
    return text


def word_count(text: str) -> int:
    """Count words as per narrator R code: str_count(abstract, '\\w+')."""
    return len(re.findall(r'\w+', text))


# ── Hedging word list (99_key_characters_words_phrases.R lines 43–87) ─────────

HEDGING_WORDS = [
    "largely", "possible", "potential", "potentially", "may", "likely",
    "could", "perhaps", "further studies", "further study",
    r"further investigations?", "future studies", "future study",
    r"future investigations?", "i believe", "i believed", "i think",
    "i thought", "we believed", "we believe", "we think", "we thought",
    "less sure", "more sure", r"seems?", r"appears?", "we attempt",
    "we attempted", "i attempt", "i attempted", "plausible",
    r"suggests?", "suggested", r"indicates?", "apparently", "generally",
    "in general", "in theory", "theoretically", "possibly", "might",
    "uncertain", "maybe",
]
# Sorted longest-first (matches R: order(-nchar)) — prevents partial shadowing
HEDGING_WORDS = sorted(HEDGING_WORDS, key=len, reverse=True)
_HEDGING_PAT = re.compile(
    '|'.join(r'\b' + w + r'\b' for w in HEDGING_WORDS),
    re.IGNORECASE,
)


# ── Signposting word list (99_key_characters_words_phrases.R lines 93–129) ────

SIGNPOSTING_WORDS = [
    "firstly", "secondly", "thirdly", "fourthly", "fifthly", "sixthly",
    "seventhly", "eighthly", "ninthly", "tenthly", "furthermore",
    "moreover", "nevertheless", "however", "finally", "already", "before",
    "soon", "afterward", "formerly", "presently", "recently", "immediately",
    "instantly", "indeed", "in turn", "after", "beforehand", "subsequently",
    "notwithstanding", "next",
]
SIGNPOSTING_WORDS = sorted(SIGNPOSTING_WORDS, key=len, reverse=True)
_SIGNPOSTING_PAT = re.compile(
    '|'.join(r'\b' + w + r'\b' for w in SIGNPOSTING_WORDS),
    re.IGNORECASE,
)


# ── Active narration (99_key_characters_words_phrases.R lines 131–136) ────────
# Case-sensitive — "We/we/Us/us" but NOT "US" (country abbreviation)

_NARRATOR_PAT = re.compile(r'\b(?:We|we|Us|us)\b')


# ── Sensational language / hype (99_key_characters_words_phrases.R lines 412–457) ──

HYPE_CATEGORIES = {
    "importance": [
        "compelling", "critical", "crucial", "essential", "foundational",
        "fundamental", "imperative", "important", "indispensable", "invaluable",
        "key", "paramount", "pivotal", "strategic", "timely", "ultimate",
        "urgent", "vital",
    ],
    "novelty": [
        "creative", "emerging", "groundbreaking", "innovative", "latest",
        "novel", "revolutionary", "unique", "unparalleled", "unprecedented",
    ],
    "rigor": [
        "accurate", "advanced", "careful", "cohesive", "detailed", "nuanced",
        "powerful", "quality", "reproducible", "rigorous", "robust",
        "scientific", "sophisticated", "strong",
    ],
    "scale": [
        "ample", "biggest", "broad", "comprehensive", "considerable", "deeper",
        "diverse", "enormous", "expansive", "extensive", "fastest", "greatest",
        "huge", "immediate", "immense", r"inter.?disciplinary", "international",
        r"inter.?professional", "largest", "massive", r"multi.?disciplinary",
        "myriad", "overwhelming", "substantial", r"trans.?disciplinary",
        "tremendous", "vast",
    ],
    "utility": [
        "accessible", "actionable", "deployable", "durable", "easy",
        "effective", "efficacious", "efficient", "generalizable",
        "generalisable", "ideal", "impactful", "intuitive", "meaningful",
        "productive", "ready", "relevant", "rich", "safer", "scalable",
        "seamless", "sustainable", "synergistic", "tailored", "tangible",
        "transformative", r"user.?friendly",
    ],
    "quality": [
        "ambitious", "collegial", "dedicated", "exceptional", "intellectual",
        r"long.?standing", "motivated", "premier", "prestigious", "promising",
        "renowned", "skilled", "stellar", "successful", "talented", "vibrant",
    ],
    "attitude": [
        "attractive", "confident", "exciting", "incredible", "interesting",
        "intriguing", "notable", "outstanding", "remarkable", "surprising",
    ],
    "problem": [
        "alarming", "daunting", "desperate", "devastating", "dire", "dismal",
        "elusive", "stark", "unanswered", "unmet",
    ],
    "additional": [
        "astonishing", "backbone", "critically", "decisive", "dramatic",
        "drastic", "exceptional", "extreme", "extremely", "frightening",
        "fundamental", "heavily", r"hot.?spots?", "imperative", "necessary",
        "persistent", "profound", "radical", "radically", "rapid", "rapidly",
        "serious", "severe", "severely", "urgently",
    ],
}

_HYPE_PATTERNS: dict[str, re.Pattern] = {}
for _cat, _words in HYPE_CATEGORIES.items():
    _words_sorted = sorted(_words, key=len, reverse=True)
    _HYPE_PATTERNS[_cat] = re.compile(
        '|'.join(r'\b' + w + r'\b' for w in _words_sorted),
        re.IGNORECASE,
    )


# ── Metric helpers ─────────────────────────────────────────────────────────────

def count_hedging(text: str) -> int:
    return len(_HEDGING_PAT.findall(text.lower()))


def count_signposting(text: str) -> int:
    return len(_SIGNPOSTING_PAT.findall(text.lower()))


def has_narrator(text: str) -> bool:
    return bool(_NARRATOR_PAT.search(text))


def count_hype(text: str) -> dict[str, int]:
    lower = text.lower()
    return {cat: len(pat.findall(lower)) for cat, pat in _HYPE_PATTERNS.items()}


def count_sentences(text: str) -> int:
    """
    Count sentence-ending full-stops as per narrator paper description:
    'tracking the frequency of full-stops, selecting only for those used at
    the end of a sentence' — i.e. full-stops followed by whitespace or end.
    """
    count = len(re.findall(r'\.\s', text))
    if text.rstrip().endswith('.'):
        count += 1
    return max(count, 1)


# ── Data loading ──────────────────────────────────────────────────────────────

def iter_venue_papers(
    processed_dir: str,
    venues: list[str],
) -> Iterator[tuple[str, dict]]:
    """Yield (venue, paper_dict) for every paper in every venue."""
    for venue in venues:
        venue_dir = os.path.join(processed_dir, venue)
        if not os.path.isdir(venue_dir):
            continue
        for fname in sorted(os.listdir(venue_dir)):
            if not fname.endswith('.json'):
                continue
            for paper in load_processed(os.path.join(venue_dir, fname)):
                yield venue, paper
