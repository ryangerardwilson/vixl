import curses
from typing import Callable, Optional

import pandas as pd


class ColumnPrompt:
    DTYPE_CHOICES = ["object", "Int64", "float64", "boolean", "datetime64[ns]"]
    _DTYPE_MAP = {
        "object": "object",
        "str": "object",
        "string": "object",
        "int": "Int64",
        "int64": "Int64",
        "integer": "Int64",
        "float": "float64",
        "float64": "float64",
        "double": "float64",
        "bool": "boolean",
        "boolean": "boolean",
        "datetime": "datetime64[ns]",
        "datetime64": "datetime64[ns]",
        "datetime64[ns]": "datetime64[ns]",
    }

    def __init__(self, state, grid, paginator, set_status_cb: Callable[[str, int], None], push_undo_cb: Optional[Callable[[], None]] = None):
        self.state = state
        self.grid = grid
        self.paginator = paginator
        self._set_status = set_status_cb
        self._push_undo_cb = push_undo_cb

        self.active = False
        self.action: Optional[str] = None  # insert_before | insert_after | rename
        self.step: Optional[str] = None  # name | dtype
        self.target_col: Optional[int] = None
        self.pending_name: Optional[str] = None
        self.buffer = ""
        self.cursor = 0
        self.hscroll = 0

    # ---------- public API ----------
    def start_insert_before(self, col_idx: int):
        self._start("insert_before", col_idx)

    def start_insert_after(self, col_idx: int):
        self._start("insert_after", col_idx)

    def start_rename(self, col_idx: int):
        self._start("rename", col_idx)

    def handle_key(self, ch):
        if not self.active:
            return

        if ch in (10, 13):  # Enter
            self._handle_enter()
            return

        if ch == 27:  # Esc
            self._set_status("Action canceled", 3)
            self._reset()
            return

        if ch in (curses.KEY_BACKSPACE, 127, 8):
            if self.cursor > 0:
                self.buffer = self.buffer[: self.cursor - 1] + self.buffer[self.cursor :]
                self.cursor -= 1
            return

        if ch == curses.KEY_LEFT:
            self.cursor = max(0, self.cursor - 1)
            return

        if ch == curses.KEY_RIGHT:
            self.cursor = min(len(self.buffer), self.cursor + 1)
            return

        if ch == curses.KEY_HOME:
            self.cursor = 0
            return

        if ch == curses.KEY_END:
            self.cursor = len(self.buffer)
            return

        if 32 <= ch <= 126:
            self.buffer = self.buffer[: self.cursor] + chr(ch) + self.buffer[self.cursor :]
            self.cursor += 1
            return

    def draw(self, win):
        if not self.active:
            return

        prompt = self._prompt_text()
        h, w = win.getmaxyx()
        text_w = max(1, w - len(prompt) - 1)

        if self.cursor < self.hscroll:
            self.hscroll = self.cursor
        elif self.cursor > self.hscroll + text_w:
            self.hscroll = self.cursor - text_w

        start = self.hscroll
        end = start + text_w
        visible = self.buffer[start:end]

        try:
            win.addnstr(0, 0, prompt, len(prompt))
            win.addnstr(0, len(prompt), visible, text_w)
            win.move(0, len(prompt) + (self.cursor - self.hscroll))
        except curses.error:
            pass
        win.refresh()

    # ---------- internals ----------
    def set_push_undo(self, cb: Optional[Callable[[], None]]):
        self._push_undo_cb = cb

    def _start(self, action: str, col_idx: int):

        self.active = True
        self.action = action
        self.target_col = col_idx
        self.step = "name"
        self.pending_name = None
        self.buffer = ""
        self.cursor = 0
        self.hscroll = 0

    def _handle_enter(self):
        text = self.buffer.strip()
        if not text:
            self._set_status("Name required", 3)
            return

        if self.step == "name":
            if self.action in ("insert_before", "insert_after"):
                if text in self.state.df.columns:
                    self._set_status("Column already exists", 3)
                    return
                self.pending_name = text
                self.step = "dtype"
                self.buffer = ""
                self.cursor = 0
                self.hscroll = 0
                return

            if self.action == "rename":
                if text in self.state.df.columns:
                    self._set_status("Column already exists", 3)
                    return
                self._apply_rename(text)
                self._reset()
                return

        elif self.step == "dtype":
            dtype = self._normalize_dtype(text)
            if not dtype:
                self._set_status(
                    "Use one of: " + "/".join(self.DTYPE_CHOICES), 4
                )
                return
            self._apply_insert(dtype)
            self._reset()
            return

    def _normalize_dtype(self, text: str) -> Optional[str]:
        return self._DTYPE_MAP.get(text.strip().lower()) if text else None

    def _default_series(self, dtype: str):
        n = len(self.state.df)
        if dtype == "object":
            return pd.Series([""] * n, dtype="object")
        if dtype == "Int64":
            return pd.Series([pd.NA] * n, dtype="Int64")
        if dtype == "float64":
            return pd.Series([float("nan")] * n, dtype="float64")
        if dtype == "boolean":
            return pd.Series([pd.NA] * n, dtype="boolean")
        if dtype == "datetime64[ns]":
            return pd.Series([pd.NaT] * n, dtype="datetime64[ns]")
        return pd.Series([pd.NA] * n)

    def _apply_insert(self, dtype: str):
        if self.pending_name is None or self.target_col is None:
            self._set_status("Missing column context", 4)
            return

        if self._push_undo_cb:
            try:
                self._push_undo_cb()
            except Exception:
                pass

        df = self.state.df
        loc = self.target_col if self.action == "insert_before" else self.target_col + 1
        loc = min(loc, len(df.columns))
        series = self._default_series(dtype)
        df.insert(loc, self.pending_name, series)
        self.grid.df = df
        self.paginator.update_total_rows(len(df))
        self.grid.curr_col = loc
        self.grid.adjust_col_viewport()
        self._set_status(f"Inserted column '{self.pending_name}'", 3)


    def _apply_rename(self, new_name: str):
        if self.target_col is None:
            self._set_status("Missing column context", 4)
            return
        cols = list(self.state.df.columns)
        if not cols:
            self._set_status("No columns to rename", 3)
            return
        if self.target_col >= len(cols):
            self._set_status("Column index out of range", 4)
            return
        old_name = cols[self.target_col]
        if self._push_undo_cb:
            try:
                self._push_undo_cb()
            except Exception:
                pass
        self.state.df.rename(columns={old_name: new_name}, inplace=True)
        self.grid.df = self.state.df
        self._set_status(f"Renamed column '{old_name}' to '{new_name}'", 3)

    def _reset(self):
        self.active = False
        self.action = None
        self.step = None
        self.target_col = None
        self.pending_name = None
        self.buffer = ""
        self.cursor = 0
        self.hscroll = 0

    def _prompt_text(self) -> str:
        if self.action in ("insert_before", "insert_after"):
            direction = "before" if self.action == "insert_before" else "after"
            if self.step == "dtype":
                return (
                    f"Insert {direction} dtype ({'/'.join(self.DTYPE_CHOICES)}): "
                )
            return f"Insert {direction} col name: "

        if self.action == "rename":
            return "Rename column to: "

        return "Column action: "
