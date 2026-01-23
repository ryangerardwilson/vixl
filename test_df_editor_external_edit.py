import os
import tempfile
from types import SimpleNamespace, MethodType

import pandas as pd

from df_editor import DfEditor
import config_paths
import df_editor_external


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


def test_external_edit_updates_cell_with_coercion():
    df = pd.DataFrame({"a": pd.Series([1], dtype="Int64")})
    editor, grid, _ = _make_editor(df)

    tmp_path = _tempfile_with_contents("42")

    def fake_prepare(_r, _c):
        return tmp_path, "1"

    editor.external._prepare_temp_file = fake_prepare

    editor.queue_external_edit()
    editor.run_pending_external_edit()

    try:
        os.unlink(tmp_path)
    except OSError:
        pass

    assert editor.state.df.iloc[0, 0] == 42
    assert grid.df.iloc[0, 0] == 42
    assert str(editor.state.df["a"].dtype) == "Int64"


def test_external_edit_trims_whitespace_and_blank_lines():
    df = pd.DataFrame({"a": pd.Series([1], dtype="Int64")})
    editor, grid, _ = _make_editor(df)

    tmp_path = _tempfile_with_contents(" \n  5 \t\n\n")

    def fake_prepare(_r, _c):
        return tmp_path, "1"

    editor.external._prepare_temp_file = fake_prepare

    editor.queue_external_edit()
    editor.run_pending_external_edit()

    try:
        os.unlink(tmp_path)
    except OSError:
        pass

    assert editor.state.df.iloc[0, 0] == 5
    assert grid.df.iloc[0, 0] == 5
    assert str(editor.state.df["a"].dtype) == "Int64"


def test_leader_conf_sequence_opens_config():
    df = pd.DataFrame({"a": [1]})
    editor, _, _ = _make_editor(df)

    calls = []

    def fake_open_config(self):
        calls.append("open")

    editor.external.open_config = MethodType(fake_open_config, editor.external)

    editor.handle_key(ord("c"))
    assert calls == []

    for ch in ",conf":
        editor.handle_key(ord(ch))

    assert calls == ["open"]


def test_open_config_invokes_refresh_on_success():
    df = pd.DataFrame({"a": [1]})
    editor, _, _ = _make_editor(df)
    refresh_calls = []
    editor.ctx.refresh_config = lambda: refresh_calls.append("refresh")

    original_dir = config_paths.CONFIG_DIR
    original_json = config_paths.CONFIG_JSON
    original_module_json = df_editor_external.CONFIG_JSON
    try:
        with tempfile.TemporaryDirectory() as tmp:
            config_paths.CONFIG_DIR = tmp
            config_paths.CONFIG_JSON = os.path.join(tmp, "config.json")
            df_editor_external.CONFIG_JSON = config_paths.CONFIG_JSON

            editor.external.open_config()
    finally:
        config_paths.CONFIG_DIR = original_dir
        config_paths.CONFIG_JSON = original_json
        df_editor_external.CONFIG_JSON = original_module_json

    assert refresh_calls == ["refresh"]


def test_open_config_does_not_refresh_on_cancel():
    df = pd.DataFrame({"a": [1]})
    editor, _, _ = _make_editor(df)
    refresh_calls = []
    editor.ctx.refresh_config = lambda: refresh_calls.append("refresh")
    editor.ctx.run_interactive = lambda argv: 1  # simulate cancel

    original_dir = config_paths.CONFIG_DIR
    original_json = config_paths.CONFIG_JSON
    original_module_json = df_editor_external.CONFIG_JSON
    try:
        with tempfile.TemporaryDirectory() as tmp:
            config_paths.CONFIG_DIR = tmp
            config_paths.CONFIG_JSON = os.path.join(tmp, "config.json")
            df_editor_external.CONFIG_JSON = config_paths.CONFIG_JSON

            editor.external.open_config()
    finally:
        config_paths.CONFIG_DIR = original_dir
        config_paths.CONFIG_JSON = original_json
        df_editor_external.CONFIG_JSON = original_module_json

    assert refresh_calls == []
