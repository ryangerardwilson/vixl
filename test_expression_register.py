from expression_register import (
    parse_expression_register_entry,
    parse_expression_register,
)


def test_parse_expression_entry_without_comment():
    entry = parse_expression_register_entry("df.foo()")
    assert entry is not None
    assert entry.kind == "expression"
    assert entry.expr == "df.foo()"
    assert entry.comment == ""
    assert entry.match_text == "df.foo()"


def test_parse_expression_entry_with_comment_outside_quotes():
    entry = parse_expression_register_entry("df.foo() # comment here")
    assert entry is not None
    assert entry.kind == "expression"
    assert entry.expr == "df.foo()"
    assert entry.comment == "comment here"
    assert entry.match_text == "df.foo() comment here"


def test_parse_expression_entry_ignores_hash_within_quotes():
    entry = parse_expression_register_entry(
        "df.foo(query='select # not comment') # real note"
    )
    assert entry is not None
    assert entry.kind == "expression"
    assert entry.expr == "df.foo(query='select # not comment')"
    assert entry.comment == "real note"


def test_parse_comment_only_entry():
    entry = parse_expression_register_entry("%fz#/important tag")
    assert entry is not None
    assert entry.kind == "comment_only"
    assert entry.expr == ""
    assert entry.comment == "important tag"
    assert entry.match_text == "important tag"


def test_parse_comment_only_entry_requires_text():
    assert parse_expression_register_entry("%fz#/") is None


def test_parse_expression_register_filters_invalid_entries():
    entries = parse_expression_register([" ", "%fz#/ ", "df.good()"])
    assert len(entries) == 1
    assert entries[0].expr == "df.good()"
