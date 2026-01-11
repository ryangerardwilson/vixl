import unittest

from types import SimpleNamespace

from df_editor import DfEditor


class DummyGrid:
    def __init__(self, col_width=6):
        self.curr_col = 0
        self.curr_row = 0
        self.col_width = col_width

    def get_col_width(self, _col):
        return self.col_width


class DummyPaginator:
    def update_total_rows(self, _):
        pass

    def ensure_row_visible(self, _):
        pass


class DfEditorCellNormalMotionTests(unittest.TestCase):
    def _editor(self, buffer_value: str, cursor: int, col_width: int = 6):
        state = SimpleNamespace(df=None)
        grid = DummyGrid(col_width=col_width)
        paginator = DummyPaginator()
        editor = DfEditor(state, grid, paginator, lambda *_: None)
        editor.mode = "cell_normal"
        editor.cell_buffer = buffer_value
        editor.cell_cursor = cursor
        editor.cell_hscroll = 0
        return editor

    def test_zero_and_dollar_move_to_line_edges(self):
        editor = self._editor("hello world", cursor=5)
        editor.handle_key(ord("0"))
        self.assertEqual(editor.cell_cursor, 0)
        self.assertEqual(editor.cell_hscroll, 0)

        editor.handle_key(ord("$"))
        self.assertEqual(editor.cell_cursor, len(editor.cell_buffer))
        self.assertGreaterEqual(editor.cell_cursor, editor.cell_hscroll)

    def test_word_forward_punctuation_separates_words(self):
        editor = self._editor("word1.word2", cursor=0)
        editor.handle_key(ord("w"))
        self.assertEqual(editor.cell_cursor, 6)  # start of word2

        editor.handle_key(ord("w"))
        self.assertEqual(editor.cell_cursor, len(editor.cell_buffer))

    def test_word_forward_skips_separators_then_to_next_word(self):
        editor = self._editor("(word1)(word2)", cursor=0)
        editor.handle_key(ord("w"))
        self.assertEqual(editor.cell_cursor, 1)  # start of word1
        editor.handle_key(ord("w"))
        self.assertEqual(editor.cell_cursor, 8)  # start of word2

    def test_word_backward_from_end_lands_at_word_starts(self):
        editor = self._editor("word1.word2", cursor=len("word1.word2"))
        editor.handle_key(ord("b"))
        self.assertEqual(editor.cell_cursor, 6)  # start of word2
        editor.handle_key(ord("b"))
        self.assertEqual(editor.cell_cursor, 0)  # start of word1

    def test_word_backward_through_separators(self):
        editor = self._editor("foo---bar", cursor=8)
        editor.handle_key(ord("b"))
        self.assertEqual(editor.cell_cursor, 6)  # start of bar
        editor.handle_key(ord("b"))
        self.assertEqual(editor.cell_cursor, 0)  # start of foo

    def test_autoscroll_updates_when_cursor_moves(self):
        editor = self._editor("abcdef", cursor=0, col_width=3)
        editor.handle_key(ord("$"))
        self.assertEqual(editor.cell_cursor, 6)
        self.assertEqual(editor.cell_hscroll, 4)


if __name__ == "__main__":
    unittest.main()
