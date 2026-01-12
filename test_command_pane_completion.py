from command_pane import CommandPane


def _apply_completion(pane: CommandPane):
    suggestion = pane._get_suggestion()
    assert suggestion is not None, "expected a completion suggestion"
    pane._apply_suggestion(suggestion)


def test_custom_df_vixl_template_inserts_full_and_sets_cursor_inside_parens():
    pane = CommandPane()
    pane.set_custom_expansions(["df.vixl.distribution_ascii_bar(bins=10)"])
    pane.set_extension_names(["multiply_cols"])
    pane.set_buffer("df.vixl.dis")

    _apply_completion(pane)

    assert pane.get_buffer() == "df.vixl.distribution_ascii_bar(bins=10)"
    assert pane.cursor == len(pane.get_buffer())


def test_extension_completion_fallback_when_no_custom_match():
    pane = CommandPane()
    pane.set_custom_expansions(["df.vixl.other()"])  # no matching prefix
    pane.set_extension_names(["multiply_cols"])
    pane.set_buffer("df.vixl.mul")

    _apply_completion(pane)

    assert pane.get_buffer() == "df.vixl.multiply_cols"
    assert pane.cursor == len(pane.get_buffer())


def test_df_base_template_inserts_and_positions_cursor():
    pane = CommandPane()
    pane.set_custom_expansions(["df.pivot()"])
    pane.set_extension_names([])
    pane.set_buffer("df.pi")

    _apply_completion(pane)

    assert pane.get_buffer() == "df.pivot()"
    # Cursor should be at the end of the inserted template
    assert pane.cursor == len(pane.get_buffer())
