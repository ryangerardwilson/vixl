from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from df_editor import DfEditor


class DummyGrid:
    def __init__(self):
        self.curr_row = 0
        self.curr_col = 0
        self.row_offset = 0
        self.col_offset = 0
        self.highlight_mode = "cell"
        self.df = None

    def adjust_col_viewport(self):
        pass


class DummyPaginator:
    def __init__(self):
        self.page_start = 0
        self.page_end = 1
        self.page_index = 0
        self.total_rows = 1

    def ensure_row_visible(self, _row):
        pass


def test_y_copies_df_and_yc_copies_cell():
    state = SimpleNamespace(
        df=pd.DataFrame({"a": [1]}),
        expand_all_rows=False,
        expanded_rows=set(),
    )
    grid = DummyGrid()
    paginator = DummyPaginator()
    editor = DfEditor(
        state, grid, paginator, lambda *args, **kwargs: None, column_prompt=None
    )
    editor.ctx.config = {"CLIPBOARD_INTERFACE_COMMAND": ["fake-clip"]}

    with patch("subprocess.run") as run:
        # , y a => yank all
        editor.handle_key(ord(","))
        editor.handle_key(ord("y"))
        editor.handle_key(ord("a"))
        assert run.call_count == 1
        assert run.call_args[0][0] == ["fake-clip"]
        df_call = run.call_args_list[0]
        assert df_call.kwargs.get("text") is True
        assert df_call.kwargs.get("input") == state.df.to_csv(sep="\t", index=False)

        # , y c => yank cell
        editor.handle_key(ord(","))
        editor.handle_key(ord("y"))
        editor.handle_key(ord("c"))
        assert run.call_count == 2
        cell_call = run.call_args_list[1]
        assert cell_call.args[0] == ["fake-clip"]
        assert cell_call.kwargs.get("text") is True
        assert cell_call.kwargs.get("input") == "1"


def test_visual_yc_copies_selection():
    df = pd.DataFrame(
        {
            "a": [1, 2, 3],
            "b": [10, 20, 30],
            "c": [100, 200, 300],
        }
    )
    state = SimpleNamespace(
        df=df,
        expand_all_rows=False,
        expanded_rows=set(),
    )
    grid = DummyGrid()
    grid.df = df  # type: ignore[attr-defined]
    paginator = DummyPaginator()
    editor = DfEditor(
        state, grid, paginator, lambda *args, **kwargs: None, column_prompt=None
    )
    editor.ctx.config = {"CLIPBOARD_INTERFACE_COMMAND": ["fake-clip"]}

    with patch("subprocess.run") as run:
        # Enter visual mode and select rows 0-1, cols 0-1
        editor.handle_key(ord("v"))
        editor.handle_key(ord("l"))
        editor.handle_key(ord("j"))

        editor.handle_key(ord(","))
        editor.handle_key(ord("y"))
        editor.handle_key(ord("c"))

        assert run.call_count == 1
        selection = df.iloc[0:2, 0:2]
        expected = selection.to_csv(sep="\t", index=False)
        call = run.call_args_list[0]
        assert call.args[0] == ["fake-clip"]
        assert call.kwargs.get("text") is True
        assert call.kwargs.get("input") == expected
