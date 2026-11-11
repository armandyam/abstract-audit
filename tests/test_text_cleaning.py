"""Tests for the LaTeX and URL normalisation behind the robustness check.

Conference abstracts carry raw markup, and the robustness analysis rests on
these rules treating it the way a reader would. None of this markup is rare
in the corpus, but the edge cases (math spliced into a word, an escaped
dollar sign) are, so they are pinned here.
"""
import pytest

from processing.text_cleaning import clean_abstract, strip_latex


def test_inline_math_becomes_one_token():
    assert clean_abstract(r"Let $n,T,\bar{d}$ denote the rank.") == "Let x denote the rank."


def test_math_drop_and_keep():
    s = r"A $19\times 19$ board."
    assert clean_abstract(s, math="drop") == "A board."
    assert "$" in strip_latex(s, math="keep")


def test_display_math_wins_over_inline():
    assert clean_abstract(r"We have $$a+b$$ here.") == "We have x here."


def test_math_spliced_inside_a_word_keeps_the_letters():
    s = r"a $\underline{Co}$llabo$\underline{ra}$tive framework"
    assert clean_abstract(s) == "a Collaborative framework"


def test_escaped_dollar_is_not_math():
    """The text between two escaped dollars is prose and must survive."""
    assert clean_abstract(r"It costs \$5 and \$6 today.") == r"It costs \$5 and \$6 today."


def test_text_commands_unwrap_nested():
    assert clean_abstract(r"We present \emph{\textbf{Coral}} (\texttt{FWC}).") == \
        "We present Coral (FWC)."


@pytest.mark.parametrize("url", ["https://github.com/a/b", "www.example.org/x",
                                 "arXiv: 1234.5678", "doi:10.1000/xyz"])
def test_urls_removed_only_when_asked(url):
    s = f"Code at {url} now."
    assert clean_abstract(s) == "Code at now."
    assert url.split()[0] in clean_abstract(s, urls=False)


def test_headings_ampersand_and_non_ascii():
    assert clean_abstract("BACKGROUND: Cats & dogs café.") == "Cats and dogs caf."
    assert clean_abstract("BACKGROUND: x", headings=False) == "BACKGROUND: x"


def test_empty_and_bad_mode():
    assert clean_abstract("") == ""
    with pytest.raises(ValueError):
        strip_latex("x", math="inline")
