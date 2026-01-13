# ~/Apps/vixl/df_editor.py
import curses
import os
import shlex
import subprocess
import tempfile
import pandas as pd

from df_editor_context import DfEditorContext, CTX_ATTRS


class DfEditor:
    """Handles dataframe editing state and key interactions."""

    def __init__(self, state, grid, paginator, set_status_cb, column_prompt=None):
        object.__setattr__(
            self,
            "ctx",
            DfEditorContext(
                state=state,
                grid=grid,
                paginator=paginator,
                _set_status=set_status_cb,
                column_prompt=column_prompt,
                _leader_ttl=1.5,
            ),
        )

    def __getattr__(self, name):
        if name in CTX_ATTRS:
            return getattr(self.ctx, name)
        raise AttributeError(name)

    def __setattr__(self, name, value):
        if name == "ctx":
            object.__setattr__(self, name, value)
            return
        if name in CTX_ATTRS:
            setattr(self.ctx, name, value)
            return
        object.__setattr__(self, name, value)

    # ---------- helpers ----------
    def _coerce_cell_value(self, col_name: str, text: str):
        text = "" if text is None else str(text)
        try:
            dtype = self.state.df[col_name].dtype
        except Exception:
            dtype = object

        stripped = text.strip()
        if pd.api.types.is_integer_dtype(dtype):
            if stripped == "":
                return pd.NA
            return int(stripped)

        if pd.api.types.is_float_dtype(dtype):
            if stripped == "":
                return float("nan")
            return float(stripped)

        if pd.api.types.is_bool_dtype(dtype):
            if stripped == "":
                return pd.NA
            lowered = stripped.lower()
            if lowered in {"1", "true", "t", "yes", "y", "on"}:
                return True
            if lowered in {"0", "false", "f", "no", "n", "off"}:
                return False
            raise ValueError(f"Cannot coerce '{text}' to boolean")

        if pd.api.types.is_datetime64_any_dtype(dtype):
            if stripped == "":
                return pd.NaT
            return pd.to_datetime(stripped, errors="raise")

        return text

    def _autoscroll_insert(self):
        cw = max(1, self.grid.get_col_width(self.grid.curr_col))
        if self.cell_cursor < self.cell_hscroll:
            self.cell_hscroll = self.cell_cursor
        elif self.cell_cursor > self.cell_hscroll + cw - 1:
            self.cell_hscroll = self.cell_cursor - (cw - 1)

        max_scroll = max(0, len(self.cell_buffer) - cw + 1)
        self.cell_hscroll = max(0, min(self.cell_hscroll, max_scroll))

    def _autoscroll_cell_normal(self, prefer_left: bool = False, margin: int = 2):
        cw = max(1, self.grid.get_rendered_col_width(self.grid.curr_col))
        lines = max(1, getattr(self.state, "row_lines", 1))
        span = max(1, cw * lines)
        buf_len = len(self.cell_buffer)

        max_scroll = max(0, buf_len - span)

        if self.cell_cursor < self.cell_hscroll:
            self.cell_hscroll = self.cell_cursor
        elif self.cell_cursor >= self.cell_hscroll + span:
            if prefer_left:
                self.cell_hscroll = max(0, self.cell_cursor - max(0, margin))
            else:
                self.cell_hscroll = self.cell_cursor - span + 1

        self.cell_hscroll = min(max(self.cell_hscroll, 0), max_scroll)

    def _is_word_char(self, ch: str) -> bool:
        return ch.isalnum() or ch == "_"

    def _cell_word_forward(self):
        buf = self.cell_buffer
        n = len(buf)
        idx = self.cell_cursor
        if idx >= n:
            return n

        def is_word(i):
            return self._is_word_char(buf[i])

        if idx < n and is_word(idx):
            while idx < n and is_word(idx):
                idx += 1
        while idx < n and not is_word(idx):
            idx += 1
        return idx

    def _cell_word_backward(self):
        buf = self.cell_buffer
        if not buf or self.cell_cursor == 0:
            return 0

        def is_word(i):
            return self._is_word_char(buf[i])

        idx = max(0, self.cell_cursor - 1)
        if not is_word(idx):
            while idx > 0 and not is_word(idx):
                idx -= 1
        while idx > 0 and is_word(idx - 1):
            idx -= 1
        return idx

    def _get_word_bounds_at_or_after(self, idx: int):
        buf = self.cell_buffer
        n = len(buf)
        if n == 0:
            return None
        i = max(0, min(idx, n - 1))

        while i < n and not self._is_word_char(buf[i]):
            i += 1
        if i >= n:
            return None

        start = i
        while start > 0 and self._is_word_char(buf[start - 1]):
            start -= 1

        end = i
        while end < n and self._is_word_char(buf[end]):
            end += 1

        return start, end

    # ---------- leader helpers ----------
    def _leader_seq(self, state: str | None) -> str:
        if not state:
            return ""
        mapping = {
            "leader": ",",
            "i": ",i",
            "ic": ",ic",
            "ir": ",ir",
            "d": ",d",
            "r": ",r",
            "rn": ",rn",
            "c": ",c",
            "x": ",x",
            "xa": ",xa",
            "y": ",y",
            "p": ",p",
        }
        return mapping.get(state, ",")

    def _show_leader_status(self, seq: str):
        if not seq:
            return
        cp = getattr(self, "column_prompt", None)
        if cp is not None and getattr(cp, "active", False):
            return
        self._set_status(f"Leader: {seq}", self._leader_ttl)

    def _build_editor_command(self, tmp_path: str, read_only: bool = False) -> str:
        editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vim"
        if read_only:
            ro_opts = (
                "-n -R -M "
                "+setlocal\ nobuflisted\ noswapfile\ buftype=nofile\ bufhidden=wipe\ "
                "nowrap\ readonly\ nomodifiable\ nonumber\ norelativenumber\ shortmess+=I"
            )
            return f"{editor} {ro_opts} {shlex.quote(tmp_path)}"
        return f"{editor} {shlex.quote(tmp_path)}"

    def _launch_in_alacritty(self, editor_cmd: str):
        try:
            proc = subprocess.Popen(
                ["alacritty", "-e", "bash", "-lc", editor_cmd]
            )
            return proc
        except FileNotFoundError:
            return None
        except Exception:
            return None

    def _open_cell_json_preview(self, row: int, col: int):
        total_rows = len(self.state.df)
        total_cols = len(self.state.df.columns)
        if total_rows == 0 or total_cols == 0:
            self._set_status("No cell to preview", 3)
            return

        r = min(max(0, row), max(0, total_rows - 1))
        c = min(max(0, col), max(0, total_cols - 1))
        val = self.state.df.iloc[r, c]

        try:
            import json
        except ImportError:
            self._set_status("JSON preview unavailable", 3)
            return

        if val is None or (hasattr(pd, "isna") and pd.isna(val)):
            text = "null"
        else:
            try:
                parsed = json.loads(val) if isinstance(val, str) else val
                text = json.dumps(parsed, indent=2, ensure_ascii=False, default=str)
            except Exception:
                text = json.dumps(val, indent=2, ensure_ascii=False, default=str)

        tmp = tempfile.NamedTemporaryFile(mode="w+", delete=False, encoding="utf-8")
        tmp_path = tmp.name
        try:
            tmp.write(text)
            tmp.flush()
        finally:
            tmp.close()

        editor_cmd = self._build_editor_command(tmp_path, read_only=True)
        proc = self._launch_in_alacritty(editor_cmd)
        if proc is None:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
            self._set_status("JSON preview failed", 3)
            return

        self._set_status("Opened JSON preview (read-only)", 3)

    def queue_external_edit(self, preserve_cell_mode: bool):


        if self.external_proc is not None:
            self._set_status("Already editing externally", 3)
            self._reset_count()
            return
        if len(self.state.df.columns) == 0 or len(self.state.df) == 0:
            self._set_status("No cell to edit", 3)
            self._reset_count()
            return

        total_rows = len(self.state.df)
        total_cols = len(self.state.df.columns)
        r = min(max(0, self.grid.curr_row), max(0, total_rows - 1))
        c = min(max(0, self.grid.curr_col), max(0, total_cols - 1))
        col = self.state.df.columns[c]

        idx_label = self.state.df.index[r] if len(self.state.df.index) > r else r
        self.pending_edit_snapshot = {
            "row": r,
            "col": c,
            "col_name": col,
            "idx_label": idx_label,
        }
        self.pending_preserve_cell_mode = preserve_cell_mode
        self.pending_external_edit = True
        self._set_status(f"Editing '{col}' at index {idx_label}", 600)
        self._reset_count()

    def run_pending_external_edit(self):
        if not self.pending_external_edit:
            return
        if self.external_proc is not None:
            return

        snap = self.pending_edit_snapshot or {}
        r = snap.get("row", self.grid.curr_row)
        c = snap.get("col", self.grid.curr_col)
        col = snap.get("col_name") or (self.state.df.columns[c] if len(self.state.df.columns) else "")

        self.pending_external_edit = False
        self.pending_edit_snapshot = None

        proc, tmp_path, base = self._start_external_edit_process(
            row_override=r,
            col_override=c,
            col_name=col,
        )
        if proc is None:
            self._set_status("Open in Alacritty failed", 3)
            self.pending_preserve_cell_mode = False
            return

        self.external_proc = proc
        self.external_tmp_path = tmp_path
        self.external_meta = {
            "row": r,
            "col": c,
            "col_name": col,
            "base": base,
            "preserve_cell_mode": self.pending_preserve_cell_mode,
        }
        self.pending_preserve_cell_mode = False

    def _start_external_edit_process(
        self,
        row_override: int,
        col_override: int,
        col_name: str,
    ):
        if len(self.state.df.columns) == 0 or len(self.state.df) == 0:
            return None, None, None

        total_rows = len(self.state.df)
        total_cols = len(self.state.df.columns)
        r = min(max(0, row_override), max(0, total_rows - 1))
        c = min(max(0, col_override), max(0, total_cols - 1))

        val = self.state.df.iloc[r, c] if total_rows > 0 else None
        base = "" if (val is None or pd.isna(val)) else str(val)

        tmp = tempfile.NamedTemporaryFile(mode="w+", delete=False, encoding="utf-8")
        tmp_path = tmp.name
        try:
            tmp.write(base)
            tmp.flush()
        finally:
            tmp.close()

        editor_cmd = self._build_editor_command(tmp_path)
        proc = self._launch_in_alacritty(editor_cmd)
        if proc is None:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
            return None, None, None
        return proc, tmp_path, base

    def _complete_external_edit_if_done(self):
        if self.external_proc is None:
            return
        if self.external_proc.poll() is None:
            return

        if not self.external_receiving:
            self.external_receiving = True
            self._set_status("Receiving new data from editor", 5)
            return

        rc = self.external_proc.returncode
        tmp_path = self.external_tmp_path
        meta = self.external_meta or {}
        self.external_proc = None
        self.external_tmp_path = None
        self.external_meta = None
        self.external_receiving = False

        base = meta.get("base", "")
        r = meta.get("row", self.grid.curr_row)
        c = meta.get("col", self.grid.curr_col)
        preserve_cell_mode = meta.get("preserve_cell_mode", False)

        col_name_raw = meta.get("col_name")
        col_name = col_name_raw if isinstance(col_name_raw, str) and col_name_raw else None
        if col_name is None:
            if len(self.state.df.columns) == 0:
                self._set_status("No columns to update", 3)
                return
            c = max(0, min(c, len(self.state.df.columns) - 1))
            col_name = str(self.state.df.columns[c])

        new_text = base
        if tmp_path:

            try:
                with open(tmp_path, "r", encoding="utf-8") as fh:
                    new_text = fh.read()
            except Exception:
                new_text = base
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

        if rc not in (0, None):
            self._set_status("Edit canceled", 3)
            return

        new_text = (new_text or "").rstrip("\n")
        if new_text == base:
            self._set_status("No changes", 2)
            if preserve_cell_mode:
                self.cell_col = col_name
                self.cell_buffer = new_text
                self.cell_cursor = 0
                self.cell_hscroll = 0
                self.mode = "cell_normal"
                self._autoscroll_cell_normal()
            self._reset_count()
            return

        try:
            self._push_undo()
            coerced = self._coerce_cell_value(col_name, new_text)
            self.state.df.iloc[r, c] = coerced
            self.grid.df = self.state.df
            self.paginator.update_total_rows(len(self.state.df))
            self.paginator.ensure_row_visible(r)
            self._set_last_action("cell_set", value=coerced)
            self.pending_count = None
            if preserve_cell_mode:
                self.cell_col = col_name
                self.cell_buffer = new_text
                self.cell_cursor = 0
                self.cell_hscroll = 0
                self.mode = "cell_normal"
                self._autoscroll_cell_normal()
            self._set_status("Cell updated (editor)", 2)

        except Exception as e:
            self._set_status(f"Cell update failed: {e}", 3)
        self._reset_count()

    # ---------- counts ----------
    def _reset_last_action(self):
        self.last_action = None

    def _set_last_action(self, action_type: str, **kwargs):
        self.last_action = {"type": action_type, **kwargs}

    def _repeat_last_action(self):
        if not self.last_action:
            self._set_status("Nothing to repeat", 2)
            return
        act = self.last_action
        t = act.get("type")
        try:
            if t == "insert_rows":
                count = act.get("count", 1)
                above = act.get("above", True)
                self._insert_rows(above=above, count=count)
            elif t == "delete_rows":
                count = act.get("count", 1)
                self._delete_rows(count)
            elif t == "adjust_row_lines":
                delta = act.get("delta", 0)
                self._adjust_row_lines(delta)
            elif t == "cell_set":
                row = self.grid.curr_row
                col = self.grid.curr_col
                val = act.get("value", "")
                self._push_undo()
                try:
                    self.state.df.iloc[row, col] = val
                except Exception:
                    self._set_status("Repeat failed", 2)
                    return
                self.grid.df = self.state.df
                self._set_status("Repeated cell edit", 2)
            elif t == "cell_clear":
                row = self.grid.curr_row
                col = self.grid.curr_col
                self._push_undo()
                try:
                    col_name = self.state.df.columns[col]
                    self.state.df.iloc[row, col] = self._coerce_cell_value(col_name, "")
                except Exception:
                    self._set_status("Repeat failed", 2)
                    return
                self.grid.df = self.state.df
                self._set_status("Repeated cell clear", 2)
            else:
                self._set_status("Nothing to repeat", 2)
        except Exception:
            self._set_status("Repeat failed", 2)

    # ---------- counts ----------
    def _reset_count(self):
        self.pending_count = None

    def _push_count_digit(self, digit: int):
        if digit < 0 or digit > 9:
            return
        if self.pending_count is None:
            self.pending_count = digit
        else:
            self.pending_count = min(9999, self.pending_count * 10 + digit)

    def _consume_count(self, default: int = 1) -> int:
        count = self.pending_count if self.pending_count is not None else default
        self.pending_count = None
        return max(1, count)

    # ---------- undo/redo ----------
    def _snapshot_state(self):
        return {
            "df": self.state.df.copy(deep=True),
            "curr_row": self.grid.curr_row,
            "curr_col": self.grid.curr_col,
            "row_offset": self.grid.row_offset,
            "col_offset": self.grid.col_offset,
            "highlight_mode": self.grid.highlight_mode,
        }

    def _restore_state(self, snap):
        self.state.df = snap["df"]
        self.grid.df = self.state.df
        self.grid.highlight_mode = snap.get("highlight_mode", "cell")
        self.paginator.update_total_rows(len(self.state.df))
        self.grid.curr_row = min(
            max(0, snap.get("curr_row", 0)), max(0, len(self.state.df) - 1)
        )
        self.grid.curr_col = min(
            max(0, snap.get("curr_col", 0)),
            max(0, len(self.state.df.columns) - 1),
        )
        self.grid.row_offset = max(0, snap.get("row_offset", 0))
        self.grid.col_offset = max(0, snap.get("col_offset", 0))
        self.paginator.ensure_row_visible(self.grid.curr_row)
        self.grid.highlight_mode = "cell"
        self.mode = "normal"
        self.cell_buffer = ""
        self.cell_cursor = 0
        self.cell_hscroll = 0
        self.pending_count = None

    def _push_undo(self):
        if not hasattr(self.state, "undo_stack"):
            return
        snap = self._snapshot_state()
        self.state.undo_stack.append(snap)
        if len(self.state.undo_stack) > getattr(self.state, "undo_max_depth", 50):
            self.state.undo_stack.pop(0)
        if hasattr(self.state, "redo_stack"):
            self.state.redo_stack.clear()

    def _push_redo(self):
        if hasattr(self.state, "redo_stack"):
            self.state.redo_stack.append(self._snapshot_state())

    def undo(self):
        if not getattr(self.state, "undo_stack", None):
            self._set_status("Nothing to undo", 2)
            self._reset_count()
            return
        current = self._snapshot_state()
        self._push_redo()
        snap = self.state.undo_stack.pop()
        self._restore_state(snap)
        remaining = len(self.state.undo_stack)
        self._set_status(f"Undone ({remaining} more)" if remaining else "Undone", 2)
        self.pending_count = None

    def redo(self):
        if not getattr(self.state, "redo_stack", None):
            self._set_status("Nothing to redo", 2)
            self._reset_count()
            return
        current = self._snapshot_state()
        if hasattr(self.state, "undo_stack"):
            self.state.undo_stack.append(current)
            if len(self.state.undo_stack) > getattr(self.state, "undo_max_depth", 50):
                self.state.undo_stack.pop(0)
        snap = self.state.redo_stack.pop()
        self._restore_state(snap)
        remaining = len(self.state.redo_stack)
        self._set_status(f"Redone ({remaining} more)" if remaining else "Redone", 2)
        self.pending_count = None

    def _enter_cell_insert_at_end(self, col, base):
        self.cell_col = col
        self.cell_buffer = base
        if not self.cell_buffer.endswith(" "):
            self.cell_buffer += " "
        self.cell_cursor = len(self.cell_buffer)
        cw = max(1, self.grid.get_rendered_col_width(self.grid.curr_col))
        self.cell_hscroll = max(0, len(self.cell_buffer) - cw + 1)
        self.mode = "cell_insert"

    def _adjust_row_lines(self, delta: int, minimum: int = 1, maximum: int = 10):
        current = self.state.row_lines
        new_value = max(minimum, min(maximum, current + delta))
        if new_value == current:
            bound = "minimum" if delta < 0 else "maximum"
            self._set_status(f"Row lines {bound} reached ({new_value})", 2)
            return
        applied_delta = new_value - current
        self.state.row_lines = new_value
        self.grid.row_offset = 0
        self._set_status(f"Row lines set to {self.state.row_lines}", 2)
        self._set_last_action("adjust_row_lines", delta=applied_delta)

    def _toggle_row_expanded(self):
        if len(self.state.df) == 0:
            self._set_status("No rows to expand", 2)
            return
        row = max(0, min(self.grid.curr_row, len(self.state.df) - 1))
        expanded = getattr(self.state, "expanded_rows", set())
        if row in expanded:
            expanded.remove(row)
            self._set_status("Row collapsed", 2)
        else:
            expanded.add(row)
            self._set_status("Row expanded", 2)
        self.state.expand_all_rows = False if not expanded else self.state.expand_all_rows
        self.grid.row_offset = 0
        self._reset_count()

    def _toggle_all_rows_expanded(self):
        self.state.expand_all_rows = not getattr(self.state, "expand_all_rows", False)
        state = "expanded" if self.state.expand_all_rows else "collapsed"
        self._set_status(f"All rows {state}", 2)
        self.grid.row_offset = 0
        self._reset_count()

    def _collapse_all_rows(self):
        self.state.expand_all_rows = False
        self.state.expanded_rows = set()
        self.grid.row_offset = 0
        self._set_status("All rows collapsed", 2)
        self._reset_count()

    def _start_insert_column(self, after: bool):
        if self.column_prompt is None:
            self._set_status("Column prompt unavailable", 3)
            return
        if len(self.state.df.columns) == 0:
            self._set_status("No columns", 3)
            return
        if after:
            self.column_prompt.start_insert_after(self.grid.curr_col)
        else:
            self.column_prompt.start_insert_before(self.grid.curr_col)

    def _insert_rows(self, above: bool, count: int = 1):
        if len(self.state.df.columns) == 0:
            self._set_status("No columns", 3)
            return
        count = max(1, count)
        self._push_undo()
        insert_at = (
            self.grid.curr_row
            if above
            else (self.grid.curr_row + 1 if len(self.state.df) > 0 else 0)
        )
        row = self.state.build_default_row()
        new_rows = pd.DataFrame([row] * count, columns=self.state.df.columns)
        self.state.df = pd.concat(
            [
                self.state.df.iloc[:insert_at],
                new_rows,
                self.state.df.iloc[insert_at:],
            ],
            ignore_index=True,
        )
        self.grid.df = self.state.df
        self.paginator.update_total_rows(len(self.state.df))
        self.paginator.ensure_row_visible(insert_at)
        self.grid.curr_row = insert_at
        self.grid.highlight_mode = "cell"
        self._set_status(
            f"Inserted {count} row{'s' if count != 1 else ''} {'above' if above else 'below'}",
            2,
        )
        self._set_last_action("insert_rows", count=count, above=above)

    def _insert_row(self, above: bool):
        self._insert_rows(above=above, count=1)

    def _start_rename_column(self):
        if self.column_prompt is None:
            self._set_status("Column prompt unavailable", 3)
            return
        if len(self.state.df.columns) == 0:
            self._set_status("No columns", 3)
            return
        self.column_prompt.start_rename(self.grid.curr_col)

    def _delete_rows(self, count: int = 1):
        total_rows = len(self.state.df)
        if total_rows == 0:
            self._set_status("No rows", 3)
            return
        count = max(1, count)
        self._push_undo()
        start = self.grid.curr_row
        end = min(total_rows, start + count)
        self.state.df = self.state.df.drop(self.state.df.index[start:end]).reset_index(
            drop=True
        )
        self.grid.df = self.state.df
        total_rows = len(self.state.df)
        self.grid.curr_row = min(start, max(0, total_rows - 1))
        self.paginator.update_total_rows(total_rows)
        if total_rows:
            self.paginator.ensure_row_visible(self.grid.curr_row)
        self.grid.highlight_mode = "cell"
        deleted = end - start
        self._set_status(f"Deleted {deleted} row{'s' if deleted != 1 else ''}", 2)
        self._set_last_action("delete_rows", count=deleted)

    def _delete_current_column(self):
        cols = list(self.state.df.columns)
        if not cols:
            self._set_status("No columns", 3)
            return
        self._push_undo()
        col_idx = self.grid.curr_col
        col_name = cols[col_idx]
        self.state.df.drop(columns=[col_name], inplace=True)
        self.grid.df = self.state.df
        total_cols = len(self.state.df.columns)
        self.grid.curr_col = min(col_idx, max(0, total_cols - 1))
        self.grid.adjust_col_viewport()
        if total_cols == 0:
            self.cell_buffer = ""
            self.cell_cursor = 0
            self.cell_hscroll = 0
            self.mode = "normal"
        self._set_status(f"Deleted column '{col_name}'", 3)
        self._set_last_action("col_delete", col_name=col_name)

    # ---------- public API ----------
    def handle_key(self, ch):
        # ---------- cell insert ----------
        if self.mode == "cell_insert":
            if ch == 27:  # Esc
                self.cell_buffer = self.cell_buffer.strip()

                r, c = self.grid.curr_row, self.grid.curr_col
                col = self.cell_col
                try:
                    self._push_undo()
                    val = self._coerce_cell_value(col, self.cell_buffer)
                    self.state.df.iloc[r, c] = val
                    self._set_last_action("cell_set", value=val)
                except Exception:
                    self._set_status(f"Invalid value for column '{col}'", 3)

                # Clean reset for normal mode
                self.cell_cursor = 0
                self.cell_hscroll = 0
                self.mode = "cell_normal"
                self._reset_count()

                return

            if ch in (curses.KEY_BACKSPACE, 127, 8):
                if self.cell_cursor > 0:
                    self.cell_buffer = (
                        self.cell_buffer[: self.cell_cursor - 1]
                        + self.cell_buffer[self.cell_cursor :]
                    )
                    self.cell_cursor -= 1
                self._autoscroll_insert()
                return

            if 0 <= ch <= 0x10FFFF:
                try:
                    ch_str = chr(ch)
                except ValueError:
                    return
                self.cell_buffer = (
                    self.cell_buffer[: self.cell_cursor]
                    + ch_str
                    + self.cell_buffer[self.cell_cursor :]
                )
                self.cell_cursor += 1
                self._autoscroll_insert()
            return

        # ---------- cell normal ----------
        if self.mode == "cell_normal":
            if ch == ord("."):
                self._repeat_last_action()
                return

            # ----- numeric prefixes (counts) in cell_normal -----
            if ch >= ord("0") and ch <= ord("9"):
                digit = ch - ord("0")
                # Leading 0 with no pending count is treated as motion to start-of-line
                if digit == 0 and self.pending_count is None:
                    self.cell_cursor = 0
                    self._autoscroll_cell_normal()
                    return
                self._push_count_digit(digit)
                return

            if self.cell_leader_state:
                state = self.cell_leader_state
                self.cell_leader_state = None

                if state == "leader":
                    if ch == ord("e"):
                        # Emulate `$` then enter insert
                        self.df_leader_state = None
                        self.cell_leader_state = None
                        self.cell_cursor = len(self.cell_buffer)
                        cw = max(
                            1, self.grid.get_rendered_col_width(self.grid.curr_col)
                        )
                        self.cell_hscroll = max(0, len(self.cell_buffer) - cw + 1)
                        self.mode = "cell_insert"
                        self._reset_count()
                        return
                    if ch == ord("v"):
                        self._show_leader_status(",v")
                        self.queue_external_edit(preserve_cell_mode=True)
                        return
                    if ch == ord("c"):
                        self.cell_leader_state = "c"
                        self._show_leader_status(self._leader_seq("c"))
                        return
                    self._show_leader_status("")
                    self._reset_count()
                    return

                    if ch == ord("c"):
                        self.cell_leader_state = "c"
                        return
                    return

                if state == "c" and ch == ord("c"):
                    self.cell_buffer = ""
                    self.cell_cursor = 0
                    self.cell_hscroll = 0
                    self.mode = "cell_insert"
                    return

            if ch == ord(","):
                self.cell_leader_state = "leader"
                return

            buf_len = len(self.cell_buffer)

            # Apply counts to motions
            count = self._consume_count() if self.pending_count is not None else 1

            old_cursor = self.cell_cursor
            new_cursor = old_cursor

            if ch == ord("h"):
                new_cursor = max(0, old_cursor - count)
            elif ch == ord("l"):
                new_cursor = min(buf_len, old_cursor + count)
            elif ch == ord("0"):
                new_cursor = 0
            elif ch == ord("$"):
                new_cursor = buf_len
            elif ch == ord("w"):
                new_cursor = old_cursor
                buf = self.cell_buffer
                for _ in range(count):
                    if new_cursor >= buf_len:
                        break
                    self.cell_cursor = new_cursor
                    next_cursor = self._cell_word_forward()
                    # If we're inside the last word, don't jump to end-of-buffer.
                    if (
                        next_cursor >= buf_len
                        and new_cursor < buf_len
                        and buf
                        and self._is_word_char(buf[new_cursor])
                    ):
                        # View-fixup: if the current word is clipped, scroll to reveal it.
                        cw = max(
                            1, self.grid.get_rendered_col_width(self.grid.curr_col)
                        )
                        lines = max(1, getattr(self.state, "row_lines", 1))
                        span = max(1, cw * lines)
                        bounds = self._get_word_bounds_at_or_after(new_cursor)
                        if bounds:
                            _, word_end = bounds
                            visible_end = self.cell_hscroll + span
                            if word_end > visible_end:
                                max_scroll = max(0, len(self.cell_buffer) - span)
                                self.cell_hscroll = min(
                                    max_scroll, max(0, word_end - span)
                                )
                        break
                    if next_cursor == new_cursor:
                        break
                    new_cursor = next_cursor
            elif ch == ord("b"):
                new_cursor = old_cursor
                for _ in range(count):
                    self.cell_cursor = new_cursor
                    new_cursor = self._cell_word_backward()

            if new_cursor != old_cursor:
                self.cell_cursor = new_cursor
                self._autoscroll_cell_normal(prefer_left=(ch in (ord("w"), ord("b"))))
                self._reset_count()
                return

            # If command executed without movement, reset any pending count
            self._reset_count()

            if ch == ord("i"):
                self.mode = "cell_insert"
                return

            if ch == 27:  # Esc - exit cell editing
                self.mode = "normal"
                self.cell_buffer = ""
                self.cell_hscroll = 0
                return

            return

        # ---------- df normal (hover) ----------
        if self.mode == "normal":
            total_rows = len(self.state.df)
            total_cols = len(self.state.df.columns)

            if ch == ord("."):
                self._repeat_last_action()
                return

            # Handle numeric prefixes in df mode
            if ch >= ord("0") and ch <= ord("9"):
                self._push_count_digit(ch - ord("0"))
                return

            # Allow leader commands even when rows are zero as long as columns exist.
            if total_cols == 0:
                self.grid.curr_row = 0
                self.grid.curr_col = 0
                self.grid.row_offset = 0
                self.grid.col_offset = 0
                self._reset_count()
                return

            if total_rows == 0:
                self.grid.curr_row = 0
                self.grid.row_offset = 0

            # Clamp cursor position
            if self.grid.curr_row >= total_rows:
                self.grid.curr_row = total_rows - 1
            if self.grid.curr_col >= total_cols:
                self.grid.curr_col = total_cols - 1

            if self.grid.row_offset > self.grid.curr_row:
                self.grid.row_offset = self.grid.curr_row
            if self.grid.col_offset > self.grid.curr_col:
                self.grid.col_offset = self.grid.curr_col

            r, c = self.grid.curr_row, self.grid.curr_col
            col = self.state.df.columns[c]
            if total_rows == 0:
                val = None
            else:
                val = self.state.df.iloc[r, c]
            base = "" if (val is None or pd.isna(val)) else str(val)

            visible_rows = max(1, self.paginator.page_end - self.paginator.page_start)
            jump_rows = max(1, round(visible_rows * 0.05))
            jump_cols = max(1, round(max(1, total_cols) * 0.20))

            if ch == ord("n") and not self.df_leader_state:
                self.cell_col = col
                self.cell_buffer = base
                self.cell_cursor = 0
                self.cell_hscroll = 0
                self.mode = "cell_normal"
                self._autoscroll_cell_normal()
                self._reset_count()
                return

            if self.df_leader_state:
                state = self.df_leader_state
                self.df_leader_state = None
                # leader chains should not clear count until a command executes

                if state == "leader":
                    if ch == ord("y"):
                        self.df_leader_state = "y"
                        self._show_leader_status(",y")
                        return

                    if ch == ord("p"):
                        self.df_leader_state = "p"
                        self._show_leader_status(",p")
                        return

                    if ch == ord("j"):
                        if total_rows == 0:
                            self._reset_count()
                            return
                        target = total_rows - 1
                        self.paginator.ensure_row_visible(target)
                        self.grid.row_offset = 0
                        self.grid.curr_row = target
                        self.grid.highlight_mode = "cell"
                        self._reset_count()
                        return

                    if ch == ord("k"):
                        if total_rows == 0:
                            self._reset_count()
                            return
                        self.paginator.ensure_row_visible(0)
                        self.grid.row_offset = 0
                        self.grid.curr_row = 0
                        self.grid.highlight_mode = "cell"
                        self._reset_count()
                        return

                    if ch == ord("h"):
                        if total_cols == 0:
                            self._reset_count()
                            return
                        self.grid.curr_col = 0
                        self.grid.adjust_col_viewport()
                        self._reset_count()
                        return

                    if ch == ord("l"):
                        if total_cols == 0:
                            self._reset_count()
                            return
                        self.grid.curr_col = total_cols - 1
                        self.grid.adjust_col_viewport()
                        self._reset_count()
                        return

                    if ch == ord("e"):
                        self._show_leader_status(",e")
                        is_expanded = getattr(self.state, "expand_all_rows", False) or (
                            self.grid.curr_row in getattr(self.state, "expanded_rows", set())
                        )
                        if is_expanded:
                            self.queue_external_edit(preserve_cell_mode=False)
                        else:
                            self._enter_cell_insert_at_end(col, base)
                        return

                    if ch == ord("v"):
                        self._show_leader_status(",v")
                        self.queue_external_edit(preserve_cell_mode=False)
                        return

                    if ch == ord("x"):
                        self.df_leader_state = "x"
                        self._show_leader_status(self._leader_seq("x"))
                        return

                    if ch == ord("i"):
                        self.df_leader_state = "i"
                        self._show_leader_status(self._leader_seq("i"))
                        return

                    if ch == ord("d"):
                        self.df_leader_state = "d"
                        self._show_leader_status(self._leader_seq("d"))
                        return

                    if ch == ord("r"):
                        self.df_leader_state = "r"
                        self._show_leader_status(self._leader_seq("r"))
                        return

                elif state == "y":
                    if ch == ord("a"):
                        try:
                            import subprocess

                            tsv_data = self.state.df.to_csv(sep="\t", index=False)
                            subprocess.run(
                                ["wl-copy"], input=tsv_data, text=True, check=True
                            )
                            self._set_status("DF copied", 3)
                        except Exception:
                            self._set_status("Copy failed", 3)
                        self._reset_count()
                        return
                    if ch == ord("c"):
                        try:
                            import subprocess

                            value = "" if (val is None or pd.isna(val)) else str(val)
                            subprocess.run(["wl-copy"], input=value, text=True, check=True)
                            self._set_status("Cell copied", 3)
                        except Exception:
                            self._set_status("Copy failed", 3)
                        self._reset_count()
                        return
                    self._reset_count()
                    return

                elif state == "p":
                    if ch == ord("j"):
                        self._open_cell_json_preview(r, c)
                        self._reset_count()
                        return
                    self._reset_count()
                    return

                if state == "i":
                    if ch == ord("c"):
                        self.df_leader_state = "ic"
                        self._show_leader_status(self._leader_seq("ic"))
                        return
                    if ch == ord("r"):
                        self.df_leader_state = "ir"
                        self._show_leader_status(self._leader_seq("ir"))
                        return
                    self._show_leader_status("")
                    return

                if state == "ic":
                    if ch == ord("a"):
                        self._show_leader_status(",ica")
                        self._start_insert_column(after=True)
                        return
                    if ch == ord("b"):
                        self._show_leader_status(",icb")
                        self._start_insert_column(after=False)
                        return
                    self._show_leader_status("")
                    return

                if state == "ir":
                    if ch == ord("a"):
                        count = self._consume_count()
                        self._show_leader_status(",ira")
                        self._insert_rows(above=True, count=count)
                        return
                    if ch == ord("b"):
                        count = self._consume_count()
                        self._show_leader_status(",irb")
                        self._insert_rows(above=False, count=count)
                        return
                    self._show_leader_status("")
                    self._reset_count()
                    return

                if state == "d":
                    if ch == ord("r"):
                        if total_rows == 0:
                            self._set_status("No rows", 3)
                            self._reset_count()
                            return
                        row_idx = self.grid.curr_row
                        count = self._consume_count()
                        self._delete_rows(count)
                        self._show_leader_status(",dr")
                        return
                    if ch == ord("c"):
                        self._show_leader_status(",dc")
                        self._delete_current_column()
                        self._reset_count()
                        return
                    self._show_leader_status("")
                    self._reset_count()
                    return

                if state == "r":
                    if ch == ord("n"):
                        self.df_leader_state = "rn"
                        self._show_leader_status(self._leader_seq("rn"))
                        return
                    self._show_leader_status("")
                    return

                if state == "rn":
                    if ch == ord("c"):
                        self._show_leader_status(",rnc")
                        self._start_rename_column()
                        return
                    self._show_leader_status("")
                    return

                if state == "x":
                    if ch == ord("r"):
                        self._show_leader_status(",xr")
                        self._toggle_row_expanded()
                        return
                    if ch == ord("a"):
                        self.df_leader_state = "xa"
                        self._show_leader_status(self._leader_seq("xa"))
                        return
                    if ch == ord("c"):
                        self._show_leader_status(",xc")
                        self._collapse_all_rows()
                        return
                    if ch == ord("+"):
                        count = self._consume_count()
                        self._show_leader_status(",x+")
                        self._adjust_row_lines(count)
                        return
                    if ch == ord("-"):
                        count = self._consume_count()
                        self._show_leader_status(",x-")
                        self._adjust_row_lines(-count)
                        return
                    self._show_leader_status("")
                    self._reset_count()
                    return

                if state == "xa":
                    if ch == ord("r"):
                        self._show_leader_status(",xar")
                        self._toggle_all_rows_expanded()
                        return
                    self._show_leader_status("")
                    self._reset_count()
                    return

                if state == "ic":
                    if ch == ord("a"):
                        self._show_leader_status(",ica")
                        self._start_insert_column(after=True)
                        self._reset_count()
                        return
                    if ch == ord("b"):
                        self._show_leader_status(",icb")
                        self._start_insert_column(after=False)
                        self._reset_count()
                        return
                    self._show_leader_status("")
                    self._reset_count()
                    return

                if state == "d":
                    if ch == ord("c"):
                        self._show_leader_status(",dc")
                        self._delete_current_column()
                        self._reset_count()
                        return
                    self._show_leader_status("")
                    self._reset_count()
                    return

                    if ch == ord("b"):
                        self._show_leader_status(",icb")
                        self._start_insert_column(after=False)
                        return
                    self._show_leader_status("")
                    return

                if state == "ir":
                    self._show_leader_status("")
                    return

                if state == "d":
                    if ch == ord("c"):
                        self._show_leader_status(",dc")
                        self._delete_current_column()
                        return
                    self._show_leader_status("")
                    return

                if state == "r":
                    if ch == ord("n"):
                        self.df_leader_state = "rn"
                        self._show_leader_status(self._leader_seq("rn"))
                        return
                    self._show_leader_status("")
                    return

                if state == "rn":
                    if ch == ord("c"):
                        self._show_leader_status(",rnc")
                        self._start_rename_column()
                        return
                    self._show_leader_status("")
                    return

            if self.cell_leader_state:
                state = self.cell_leader_state
                self.cell_leader_state = None

            if self.cell_leader_state:
                state = self.cell_leader_state
                self.cell_leader_state = None

                if state == "leader":
                    if ch == ord("e"):
                        is_expanded = getattr(self.state, "expand_all_rows", False) or (
                            self.grid.curr_row in getattr(self.state, "expanded_rows", set())
                        )
                        if is_expanded:
                            self._show_leader_status(",v")
                            self.queue_external_edit(preserve_cell_mode=True)
                            return
                        # Emulate `$` then enter insert
                        self.df_leader_state = None
                        self.cell_leader_state = None
                        self.cell_cursor = len(self.cell_buffer)
                        cw = max(
                            1, self.grid.get_rendered_col_width(self.grid.curr_col)
                        )
                        self.cell_hscroll = max(0, len(self.cell_buffer) - cw + 1)
                        self.mode = "cell_insert"
                        self._reset_count()
                        return
                    if ch == ord("v"):
                        self._show_leader_status(",v")
                        self.queue_external_edit(preserve_cell_mode=True)
                        return
                    if ch == ord("c"):
                        self.cell_leader_state = "c"
                        self._show_leader_status(self._leader_seq("c"))
                        return
                    if ch == ord("e"):
                        self.cell_leader_state = "ce"
                        self._show_leader_status(",ce")
                        return
                    self._show_leader_status("")
                    return

                if state == "c" and ch == ord("c"):
                    self.cell_col = col
                    self.cell_buffer = ""
                    self.cell_cursor = 0
                    self.cell_hscroll = 0
                    self.mode = "cell_insert"
                    self._show_leader_status(",cc")
                    return

                if state == "ce":
                    # future cell-level expansions could live here; no-op for now
                    self._show_leader_status("")
                    return

                self._show_leader_status("")
                return

            if ch == ord(","):
                self.df_leader_state = "leader"
                self.cell_leader_state = None
                # preserve pending_count for leader chains
                self._show_leader_status(self._leader_seq("leader"))
                return

            if ch == ord("x"):
                if total_rows == 0 or total_cols == 0:
                    return
                self._push_undo()
                r, c = self.grid.curr_row, self.grid.curr_col
                col_name = self.state.df.columns[c]
                try:
                    self.state.df.iloc[r, c] = self._coerce_cell_value(col_name, "")
                except Exception:
                    self.state.df.iloc[r, c] = ""
                self._set_status("Cell cleared", 2)
                self._reset_count()
                return

            if ch == ord("i"):
                is_expanded = getattr(self.state, "expand_all_rows", False) or (
                    self.grid.curr_row in getattr(self.state, "expanded_rows", set())
                )
                if is_expanded:
                    self.queue_external_edit(preserve_cell_mode=False)
                    return
                self.cell_col = col
                self.cell_buffer = base
                if not self.cell_buffer.endswith(" "):
                    self.cell_buffer += " "
                self.cell_cursor = len(self.cell_buffer) - 1
                self.mode = "cell_insert"
                self._reset_count()
                return

                self._push_undo()
                r, c = self.grid.curr_row, self.grid.curr_col
                col_name = self.state.df.columns[c]
                try:
                    self.state.df.iloc[r, c] = self._coerce_cell_value(col_name, "")
                except Exception:
                    self.state.df.iloc[r, c] = ""
                self._set_status("Cell cleared", 2)
                self._set_last_action("cell_clear")
                return

            if ch == ord("i"):
                self.cell_col = col
                self.cell_buffer = base
                if not self.cell_buffer.endswith(" "):
                    self.cell_buffer += " "
                self.cell_cursor = len(self.cell_buffer) - 1
                self.mode = "cell_insert"
                self._reset_count()
                return

            had_count = self.pending_count is not None
            count = self._consume_count() if had_count else 1

            # Undo / Redo (ignore counts)
            if ch == ord("u"):
                self.undo()
                return
            if ch == ord("r"):
                self.redo()
                return

            # Big jumps
            if ch == 10:  # Ctrl+J - down
                if total_rows > 0:
                    step = max(1, jump_rows * count)
                    target = min(total_rows - 1, self.grid.curr_row + step)
                    self.paginator.ensure_row_visible(target)
                    self.grid.row_offset = 0
                    self.grid.curr_row = target
                return

            if ch == 11:  # Ctrl+K - up
                if total_rows > 0:
                    step = max(1, jump_rows * count)
                    target = max(0, self.grid.curr_row - step)
                    self.paginator.ensure_row_visible(target)
                    self.grid.row_offset = 0
                    self.grid.curr_row = target
                return

            if ch == 8:  # Ctrl+H - left jump
                if total_cols > 0:
                    step = max(1, jump_cols * count)
                    target = max(0, self.grid.curr_col - step)
                    self.grid.curr_col = target
                    self.grid.adjust_col_viewport()
                return

            if ch == 12:  # Ctrl+L - right jump
                if total_cols > 0:
                    step = max(1, jump_cols * count)
                    target = min(total_cols - 1, self.grid.curr_col + step)
                    self.grid.curr_col = target
                    self.grid.adjust_col_viewport()
                return

            # Normal vim movement
            if ch == ord("h"):
                target = max(0, self.grid.curr_col - count)
                self.grid.curr_col = target
                self.grid.adjust_col_viewport()
            elif ch == ord("l"):
                target = min(total_cols - 1, self.grid.curr_col + count)
                self.grid.curr_col = target
                self.grid.adjust_col_viewport()
            elif ch == ord("j"):
                if total_rows > 0:
                    target = min(total_rows - 1, self.grid.curr_row + count)
                    self.paginator.ensure_row_visible(target)
                    self.grid.row_offset = 0
                    self.grid.curr_row = target
            elif ch == ord("k"):
                if total_rows > 0:
                    target = max(0, self.grid.curr_row - count)
                    self.paginator.ensure_row_visible(target)
                    self.grid.row_offset = 0
                    self.grid.curr_row = target

            return
