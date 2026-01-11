import unittest
import unittest
from types import SimpleNamespace

import pandas as pd

from df_editor import DfEditor


class DummyGrid:
    def __init__(self, col_width=6):
        self.curr_col = 0
        self.curr_row = 0
        self.col_width = col_width
        self.df = None
        self.row_offset = 0
        self.col_offset = 0
        self.highlight_mode = "cell"

    def get_col_width(self, _col):
        return self.col_width

    def adjust_col_viewport(self):
        pass

    def move_left(self):
        self.curr_col = max(0, self.curr_col - 1)

    def move_right(self):
        self.curr_col += 1

    def move_up(self):
        self.curr_row = max(0, self.curr_row - 1)

    def move_down(self):
        self.curr_row += 1

    def move_row_down(self):
        self.curr_row += 1

    def move_row_up(self):
        self.curr_row = max(0, self.curr_row - 1)

    def move_col_left(self):
        self.curr_col = max(0, self.curr_col - 1)

    def move_col_right(self):
        self.curr_col += 1


class DummyPaginator:
    def __init__(self):
        self.page_start = 0
        self.page_end = 1
        self.page_index = 0
        self.page_count = 1
        self.total_rows = 1

    def update_total_rows(self, total):
        self.total_rows = total
        self.page_end = max(1, min(self.page_start + 1, total))

    def ensure_row_visible(self, _):
        pass

    def next_page(self):
        pass

    def prev_page(self):
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


class DfEditorDfNormalCommandTests(unittest.TestCase):
    def _df_editor(self, df):
        state = SimpleNamespace(df=df, file_path=None, file_handler=None)
        grid = DummyGrid()
        grid.df = df
        paginator = DummyPaginator()
        return DfEditor(state, grid, paginator, lambda *_: None)

    def test_n_enters_cell_normal_with_buffer(self):
        df = SimpleNamespace(columns=["a"], __len__=lambda self: 1)
        df_obj = SimpleNamespace(df=pd.DataFrame({"a": ["hi"]}))
        # reuse actual df for values
        df = df_obj.df
        editor = self._df_editor(df)
        editor.grid.curr_row = 0
        editor.grid.curr_col = 0
        editor.mode = "normal"

        editor.handle_key(ord("n"))

        self.assertEqual(editor.mode, "cell_normal")
        self.assertEqual(editor.cell_buffer, "hi")
        self.assertEqual(editor.cell_cursor, len("hi"))

    def test_delete_column_via_leader(self):
        df = pd.DataFrame({"a": [1], "b": [2]})
        editor = self._df_editor(df)
        editor.grid.curr_col = 0
        editor.mode = "normal"

        editor.handle_key(ord(","))
        editor.handle_key(ord("d"))
        editor.handle_key(ord("c"))

        self.assertEqual(list(df.columns), ["b"])
        self.assertEqual(editor.grid.curr_col, 0)


if __name__ == "__main__":
    unittest.main()
