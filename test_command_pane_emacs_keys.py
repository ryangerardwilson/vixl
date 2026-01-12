from command_pane import CommandPane


def _feed(pane: CommandPane, keys):
    pane.activate()
    for k in keys:
        pane.handle_key(k)


def test_alt_f_moves_over_paren_separated_words():
    pane = CommandPane()
    pane.set_buffer("(word1)(word2)(word3)")
    pane.cursor = 0
    _feed(pane, [27, ord("f")])  # Alt+f
    assert pane.cursor == len("(word1)")


def test_alt_b_moves_back_over_paren_separated_words():
    pane = CommandPane()
    text = "(word1)(word2)(word3)"
    pane.set_buffer(text)
    pane.cursor = len(text)
    _feed(pane, [27, ord("b")])  # Alt+b
    assert pane.cursor == len("(word1)(word2)")


def test_ctrl_w_deletes_prev_word_with_separators():
    pane = CommandPane()
    pane.set_buffer("foo,bar baz")
    pane.cursor = len("foo,bar baz")
    _feed(pane, [23])  # Ctrl+W
    assert pane.get_buffer() == "foo,"
    assert pane.cursor == len("foo,")


def test_ctrl_u_kills_to_start():
    pane = CommandPane()
    pane.set_buffer("abc def")
    pane.cursor = len("abc de")
    _feed(pane, [21])  # Ctrl+U
    assert pane.get_buffer() == "f"
    assert pane.cursor == 0


def test_esc_alone_cancels():
    pane = CommandPane()
    pane.activate()
    pane.set_buffer("something")
    res = pane.handle_key(27)
    # second call to simulate no meta follow-up should cancel
    res2 = pane.handle_key(ord("z"))
    assert res is None
    assert res2 == "cancel"
    assert pane.get_buffer() == ""
    assert pane.cursor == 0
