import unittest
from types import SimpleNamespace

import pandas as pd

from df_editor import DfEditor


class DummyGrid:
    def __init__(self):
        self.curr_col = 0
        self.curr_row = 0
        self.col_width = 6
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


class RowInsertLeaderTests(unittest.TestCase):
    def _editor(self, df, row=0):
        state = SimpleNamespace(
            df=df,
            file_path=None,
            file_handler=None,
            build_default_row=lambda: {"a": None},
        )
        grid = DummyGrid()
        grid.df = df
        grid.curr_row = row
        paginator = DummyPaginator()
        messages = []
        editor = DfEditor(state, grid, paginator, lambda m, _: messages.append(m))
        return editor, messages, df

    def test_insert_row_above(self):
        df = pd.DataFrame({"a": [1, 2]})
        editor, _, _ = self._editor(df, row=1)

        editor.handle_key(ord(","))
        editor.handle_key(ord("i"))
        editor.handle_key(ord("r"))
        editor.handle_key(ord("a"))

        self.assertEqual(len(editor.state.df), 3)
        self.assertEqual(editor.grid.curr_row, 1)

    def test_insert_row_below(self):
        df = pd.DataFrame({"a": [1]})
        editor, _, _ = self._editor(df, row=0)

        editor.handle_key(ord(","))
        editor.handle_key(ord("i"))
        editor.handle_key(ord("r"))
        editor.handle_key(ord("b"))

        self.assertEqual(len(editor.state.df), 2)
        self.assertEqual(editor.grid.curr_row, 1)


if __name__ == "__main__":
    unittest.main()
