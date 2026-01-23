from command_pane import CommandPane


def _apply_completion(pane: CommandPane):
    suggestion = pane._get_suggestion()
    assert suggestion is not None, "expected a completion suggestion"
    pane._apply_suggestion(suggestion)


def test_expression_register_df_vixl_template_inserts_full_and_sets_cursor_inside_parens():
    pane = CommandPane()
    pane.set_expression_register(["df.vixl.distribution_ascii_bar(bins=10) #chart"])
    pane.set_extension_names(["multiply_cols"])
    pane.set_buffer("df.vixl.dis")

    _apply_completion(pane)

    assert pane.get_buffer() == "df.vixl.distribution_ascii_bar(bins=10)"
    assert pane.cursor == len(pane.get_buffer())


def test_extension_completion_fallback_when_no_expression_register_match():
    pane = CommandPane()
    pane.set_expression_register(["df.vixl.other()"])
    pane.set_extension_names(["multiply_cols"])
    pane.set_buffer("df.vixl.mul")

    _apply_completion(pane)

    assert pane.get_buffer() == "df.vixl.multiply_cols"
    assert pane.cursor == len(pane.get_buffer())


def test_df_base_template_inserts_and_positions_cursor_from_expression_register():
    pane = CommandPane()
    pane.set_expression_register(["df.pivot() # pivot"])
    pane.set_extension_names([])
    pane.set_buffer("df.pi")

    _apply_completion(pane)

    assert pane.get_buffer() == "df.pivot()"
    # Cursor should be at the end of the inserted template
    assert pane.cursor == len(pane.get_buffer())


def test_exclamation_prefix_no_longer_completes_commands():
    pane = CommandPane()
    pane.set_expression_register(["df.foo()"])
    pane.set_extension_names([])
    pane.set_buffer("!foo")

    assert pane._get_suggestion() is None
