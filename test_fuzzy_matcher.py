from orchestrator import fuzzy_best_match


def test_fuzzy_favors_strong_phrase_inside_long_sentence():
    query = "vry nce dy"
    candidates = [
        "very noisy data",
        "hello world this is a very nice day",
        "some unrelated text",
    ]
    best = fuzzy_best_match(query, candidates)
    assert best == "hello world this is a very nice day"


def test_fuzzy_exact_match_wins_over_similar_options():
    query = "df.pivot_table(index='a')"
    candidates = [
        "df.pivot_table(index='a')",
        "df.pivot(index='a')",
        "df.pivot_table(index='b')",
    ]
    best = fuzzy_best_match(query, candidates)
    assert best == "df.pivot_table(index='a')"


def test_fuzzy_handles_case_insensitivity_and_abbreviation():
    query = "VRY NICE"
    candidates = [
        "very noisy",
        "very nice day",
    ]
    best = fuzzy_best_match(query, candidates)
    assert best == "very nice day"


def test_fuzzy_returns_none_when_query_or_register_invalid():
    assert fuzzy_best_match("", ["anything"]) is None
    assert fuzzy_best_match("something", []) is None
