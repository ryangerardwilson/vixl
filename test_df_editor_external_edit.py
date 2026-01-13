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


class DummyProc:
    def __init__(self, returncode=0):
        self.returncode = returncode

    def poll(self):
        return self.returncode


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
    return editor, grid, messages


def _complete_external_edit(editor, tmp_path, meta_overrides=None):
    meta = {
        "row": 0,
        "col": 0,
        "col_name": "a",
        "base": "",
        "preserve_cell_mode": False,
    }
    if meta_overrides:
        meta.update(meta_overrides)

    editor.external_proc = DummyProc()
    editor.external_tmp_path = tmp_path
    editor.external_meta = meta
    editor.external_receiving = False

    # first call flips into "receiving" state
    editor._complete_external_edit_if_done()
    # second call performs the actual read + commit
    editor._complete_external_edit_if_done()


def test_external_edit_updates_string_cell():
    df = pd.DataFrame({"a": ["old"]})
    editor, grid, _ = _make_editor(df)

    tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8")
    try:
        tmp.write("new value")
        tmp.close()

        _complete_external_edit(
            editor,
            tmp.name,
            meta_overrides={"base": "old"},
        )
    finally:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)

    assert editor.state.df.iloc[0, 0] == "new value"
    assert grid.df.iloc[0, 0] == "new value"


def test_external_edit_coerces_int64_column():
    df = pd.DataFrame({"a": pd.Series([pd.NA], dtype="Int64")})
    editor, _, _ = _make_editor(df)

    tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8")
    try:
        tmp.write("42")
        tmp.close()

        _complete_external_edit(
            editor,
            tmp.name,
            meta_overrides={"base": "", "col_name": "a"},
        )
    finally:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)

    assert editor.state.df.iloc[0, 0] == 42
    assert str(editor.state.df["a"].dtype) == "Int64"
