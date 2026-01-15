from expression_register import parse_expression_register_entry
from orchestrator import fuzzy_best_match


def _entry(value):
    return parse_expression_register_entry(value)


def test_fuzzy_favors_strong_phrase_inside_long_sentence():
    query = "vry nce dy"
    entries = [
        _entry("very noisy data"),
        _entry("hello world this is a very nice day"),
        _entry("some unrelated text"),
    ]
    best = fuzzy_best_match(query, entries)
    assert best is not None
    assert best.expr == "hello world this is a very nice day"


def test_fuzzy_exact_match_wins_over_similar_options():
    query = "df.pivot_table(index='a')"
    entries = [
        _entry("df.pivot_table(index='a')"),
        _entry("df.pivot(index='a')"),
        _entry("df.pivot_table(index='b')"),
    ]
    best = fuzzy_best_match(query, entries)
    assert best is not None
    assert best.expr == "df.pivot_table(index='a')"


def test_fuzzy_handles_case_insensitivity_and_abbreviation():
    query = "VRY NICE"
    entries = [
        _entry("very noisy"),
        _entry("very nice day"),
    ]
    best = fuzzy_best_match(query, entries)
    assert best is not None
    assert best.expr == "very nice day"


def test_fuzzy_returns_none_when_query_invalid():
    entries = [_entry("df.foo()")]
    assert fuzzy_best_match("", entries) is None


def test_fuzzy_matches_trailing_comments_but_loads_expression():
    query = "serviceability logs"
    entries = [
        _entry("df.foo() # something else"),
        _entry(
            "df.vixl.wiom_data(source='genie1_prod',query='select * from logs') #serviceability logs"
        ),
    ]
    best = fuzzy_best_match(query, entries)
    assert best is not None
    assert best.expr.startswith("df.vixl.wiom_data")
    assert best.comment == "serviceability logs"


def test_fuzzy_matches_comment_only_but_returns_entry_kind():
    query = "important tag"
    entries = [
        _entry("df.foo()"),
        _entry("%fz#/important tag"),
    ]
    best = fuzzy_best_match(query, entries)
    assert best is not None
    assert best.kind == "comment_only"
