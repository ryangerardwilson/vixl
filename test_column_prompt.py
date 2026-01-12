import unittest
from types import SimpleNamespace

import pandas as pd

from column_prompt import ColumnPrompt


class DummyGrid:
    def __init__(self):
        self.curr_col = 0
        self.df = pd.DataFrame()

    def adjust_col_viewport(self):
        pass


class DummyPaginator:
    def update_total_rows(self, _):
        pass


class ColumnPromptTests(unittest.TestCase):
    def _prompt(self, df, curr_col=0):
        grid = DummyGrid()
        grid.df = df
        grid.curr_col = curr_col
        paginator = DummyPaginator()
        messages = []
        prompt = ColumnPrompt(
            SimpleNamespace(df=df), grid, paginator, lambda m, _: messages.append(m)
        )
        grid.df = df
        return prompt, grid, messages

    def _type_and_enter(self, prompt: ColumnPrompt, text: str):
        for ch in text:
            prompt.handle_key(ord(ch))
        prompt.handle_key(10)

    def test_insert_before_adds_column_and_moves_cursor(self):
        df = pd.DataFrame({"a": [1], "b": [2]})
        prompt, grid, _ = self._prompt(df, curr_col=1)

        prompt.start_insert_before(col_idx=1)
        self._type_and_enter(prompt, "c")  # name
        self._type_and_enter(prompt, "int")  # dtype -> Int64

        self.assertFalse(prompt.active)
        self.assertEqual(list(df.columns), ["a", "c", "b"])
        self.assertEqual(grid.curr_col, 1)
        self.assertEqual(str(df["c"].dtype), "Int64")

    def test_insert_after_uses_dtype_and_places_cursor(self):
        df = pd.DataFrame({"a": [1], "b": [2]})
        prompt, grid, _ = self._prompt(df, curr_col=0)

        prompt.start_insert_after(col_idx=0)
        self._type_and_enter(prompt, "c")
        self._type_and_enter(prompt, "float")

        self.assertEqual(list(df.columns), ["a", "c", "b"])
        self.assertEqual(grid.curr_col, 1)
        self.assertEqual(str(df["c"].dtype), "float64")

    def test_rename_changes_column_name(self):
        df = pd.DataFrame({"a": [1], "b": [2]})
        prompt, grid, _ = self._prompt(df, curr_col=0)

        prompt.start_rename(col_idx=0)
        self._type_and_enter(prompt, "alpha")

        self.assertEqual(list(df.columns), ["alpha", "b"])
        self.assertEqual(grid.df.columns[0], "alpha")


if __name__ == "__main__":
    unittest.main()
