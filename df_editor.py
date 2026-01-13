# ~/Apps/vixl/df_editor.py
import curses
import os
import shlex
import pandas as pd

from df_editor_context import DfEditorContext, CTX_ATTRS
from df_editor_counts import DfEditorCounts
from df_editor_cell import DfEditorCell
from df_editor_external import DfEditorExternal
from df_editor_undo import DfEditorUndo


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
        object.__setattr__(self, "counts", DfEditorCounts(self.ctx))
        object.__setattr__(self, "undo_mgr", DfEditorUndo(self.ctx, self.counts))
        object.__setattr__(
            self,
            "cell",
            DfEditorCell(
                ctx=self.ctx,
                counts=self.counts,
                push_undo_cb=self._push_undo,
                set_last_action_cb=self._set_last_action,
                repeat_last_action_cb=self._repeat_last_action,
                leader_seq_cb=self._leader_seq,
                show_leader_status_cb=self._show_leader_status,
                queue_external_edit_cb=self._queue_external_edit_internal,
            ),
        )
        object.__setattr__(
            self,
            "external",
            DfEditorExternal(
                ctx=self.ctx,
                counts=self.counts,
                cell=self.cell,
                push_undo_cb=self._push_undo,
                set_last_action_cb=self._set_last_action,
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

    # Explicit property forwarding for the public surface used outside this module.
    # These properties keep Orchestrator/tests stable while we refactor internals.
    @property
    def state(self):
        return self.ctx.state

    @state.setter
    def state(self, value):
        self.ctx.state = value

    @property
    def grid(self):
        return self.ctx.grid

    @grid.setter
    def grid(self, value):
        self.ctx.grid = value

    @property
    def paginator(self):
        return self.ctx.paginator

    @paginator.setter
    def paginator(self, value):
        self.ctx.paginator = value

    @property
    def _set_status(self):
        return self.ctx._set_status

    @_set_status.setter
    def _set_status(self, value):
        self.ctx._set_status = value

    @property
    def column_prompt(self):
        return self.ctx.column_prompt

    @column_prompt.setter
    def column_prompt(self, value):
        self.ctx.column_prompt = value

    @property
    def _leader_ttl(self):
        return self.ctx._leader_ttl

    @_leader_ttl.setter
    def _leader_ttl(self, value):
        self.ctx._leader_ttl = value

    @property
    def mode(self):
        return self.ctx.mode

    @mode.setter
    def mode(self, value):
        self.ctx.mode = value

    @property
    def cell_buffer(self):
        return self.ctx.cell_buffer

    @cell_buffer.setter
    def cell_buffer(self, value):
        self.ctx.cell_buffer = value

    @property
    def cell_cursor(self):
        return self.ctx.cell_cursor

    @cell_cursor.setter
    def cell_cursor(self, value):
        self.ctx.cell_cursor = value

    @property
    def cell_hscroll(self):
        return self.ctx.cell_hscroll

    @cell_hscroll.setter
    def cell_hscroll(self, value):
        self.ctx.cell_hscroll = value

    @property
    def pending_count(self):
        return self.ctx.pending_count

    @pending_count.setter
    def pending_count(self, value):
        self.ctx.pending_count = value

    # ---------- helpers ----------
    def _coerce_cell_value(self, col_name: str, text: str):
        return self.cell._coerce_cell_value(col_name, text)

    def _autoscroll_insert(self):
        self.cell._autoscroll_insert()

    def _autoscroll_cell_normal(self, prefer_left: bool = False, margin: int = 2):
        self.cell._autoscroll_cell_normal(prefer_left=prefer_left, margin=margin)

    def _is_word_char(self, ch: str) -> bool:
        return self.cell._is_word_char(ch)

    def _cell_word_forward(self):
        return self.cell._cell_word_forward()

    def _cell_word_backward(self):
        return self.cell._cell_word_backward()

    def _get_word_bounds_at_or_after(self, idx: int):
        return self.cell._get_word_bounds_at_or_after(idx)

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

    def _open_cell_json_preview(self, row: int, col: int):
        self.external.open_cell_json_preview(row, col)

    def queue_external_edit(self, preserve_cell_mode: bool):
        self.external.queue_external_edit(preserve_cell_mode)

    def _queue_external_edit_internal(self, preserve_cell_mode: bool):
        """Internal helper so cell controller can queue edits without recursion."""
        self.external.queue_external_edit(preserve_cell_mode)

    def run_pending_external_edit(self):
        self.external.run_pending_external_edit()

    def _complete_external_edit_if_done(self):
        self.external.complete_external_edit_if_done()

    # ---------- counts ----------
    def _reset_last_action(self):
        self.undo_mgr.reset_last_action()

    def _set_last_action(self, action_type: str, **kwargs):
        self.undo_mgr.set_last_action(action_type, **kwargs)

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
        self.counts.reset()

    def _push_count_digit(self, digit: int):
        self.counts.push_digit(digit)

    def _consume_count(self, default: int = 1) -> int:
        return self.counts.consume(default)

    # ---------- undo/redo ----------
    def _snapshot_state(self):
        return self.undo_mgr.snapshot_state()

    def _restore_state(self, snap):
        self.undo_mgr.restore_state(snap)

    def _push_undo(self):
        self.undo_mgr.push_undo()

    def _push_redo(self):
        self.undo_mgr.push_redo()

    def undo(self):
        self.undo_mgr.undo()

    def redo(self):
        self.undo_mgr.redo()

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

        # ---------- df normal (hover) ----------
        if self.cell.handle_key(ch):
            return

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
