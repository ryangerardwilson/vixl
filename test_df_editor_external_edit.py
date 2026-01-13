import os
import tempfile
from types import SimpleNamespace

import pandas as pd

from df_editor import DfEditor


class DummyGrid:
    def __init__(self, df):
        self.df = df
        self.curr_row = 0
        self.curr_col = 0
        self.row_offset = 0
        self.col_offset = 0
        self.highlight_mode = "cell"

    def get_col_width(self, _col):
        return 10

    def get_rendered_col_width(self, _col):
        return 10

    def adjust_col_viewport(self):
        pass


class DummyPaginator:
    def __init__(self):
        self.page_start = 0
        self.page_end = 1
        self.page_index = 0
        self.page_count = 1
        self.total_rows = 0

    def update_total_rows(self, total):
        self.total_rows = total
        self.page_end = max(1, min(self.page_start + 1, total))

    def ensure_row_visible(self, _row):
        pass


def _make_editor(df):
    state = SimpleNamespace(
        df=df,
        row_lines=1,
        expanded_rows=set(),
        expand_all_rows=False,
        undo_stack=[],
        redo_stack=[],
        undo_max_depth=10,
    )
    grid = DummyGrid(df)
    paginator = DummyPaginator()
    messages = []
    editor = DfEditor(state, grid, paginator, lambda msg, _=None: messages.append(msg))
    # Run external editor synchronously without launching a real editor
    editor.ctx.run_interactive = lambda argv: 0
    return editor, grid, messages


def _tempfile_with_contents(text: str) -> str:
    tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8")
    tmp.write(text)
    tmp.close()
    return tmp.name


def test_external_edit_updates_string_cell():
    df = pd.DataFrame({"a": ["old"]})
    editor, grid, _ = _make_editor(df)

    tmp_path = _tempfile_with_contents("new value")

    def fake_prepare(_r, _c):
        return tmp_path, "old"

    editor.external._prepare_temp_file = fake_prepare

    editor.queue_external_edit(False)
    editor.run_pending_external_edit()

    try:
        os.unlink(tmp_path)
    except OSError:
        pass

    assert editor.state.df.iloc[0, 0] == "new value"
    assert grid.df.iloc[0, 0] == "new value"


def test_external_edit_coerces_int64_column():
    df = pd.DataFrame({"a": pd.Series([pd.NA], dtype="Int64")})
    editor, grid, _ = _make_editor(df)

    tmp_path = _tempfile_with_contents("42")
    editor.external._prepare_temp_file = lambda _r, _c: (tmp_path, "")

    editor.queue_external_edit(False)
    editor.run_pending_external_edit()

    try:
        os.unlink(tmp_path)
    except OSError:
        pass

    assert editor.state.df.iloc[0, 0] == 42
    assert grid.df.iloc[0, 0] == 42
    assert str(editor.state.df["a"].dtype) == "Int64"
