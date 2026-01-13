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
from df_editor_df_ops import DfEditorDfOps
from df_editor_df_mode import DfEditorDfMode


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
            "df_ops",
            DfEditorDfOps(
                ctx=self.ctx,
                counts=self.counts,
                undo_mgr=self.undo_mgr,
            ),
        )
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
        object.__setattr__(
            self,
            "df_mode",
            DfEditorDfMode(
                ctx=self.ctx,
                counts=self.counts,
                undo_mgr=self.undo_mgr,
                cell=self.cell,
                external=self.external,
                df_ops=self.df_ops,
                show_leader_status_cb=self._show_leader_status,
                leader_seq_cb=self._leader_seq,
                queue_external_edit_cb=self._queue_external_edit_internal,
                open_json_preview_cb=self._open_cell_json_preview,
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

    def _value_is_na(self, v) -> bool:
        try:
            return pd.isna(v)
        except Exception:
            return False

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
        self.df_ops.enter_cell_insert_at_end(col, base)

    def _adjust_row_lines(self, delta: int, minimum: int = 1, maximum: int = 10):
        self.df_ops.adjust_row_lines(delta, minimum=minimum, maximum=maximum)

    def _toggle_row_expanded(self):
        self.df_ops.toggle_row_expanded()

    def _toggle_all_rows_expanded(self):
        self.df_ops.toggle_all_rows_expanded()

    def _collapse_all_rows(self):
        self.df_ops.collapse_all_rows()

    def _start_insert_column(self, after: bool):
        self.df_ops.start_insert_column(after)

    def _insert_rows(self, above: bool, count: int = 1):
        self.df_ops.insert_rows(above, count)

    def _insert_row(self, above: bool):
        self.df_ops.insert_row(above)

    def _start_rename_column(self):
        self.df_ops.start_rename_column()

    def _delete_rows(self, count: int = 1):
        self.df_ops.delete_rows(count)

    def _delete_current_column(self):
        self.df_ops.delete_current_column()

    # ---------- public API ----------
    def handle_key(self, ch):
        # Delegate to appropriate handler based on mode
        if self.cell.handle_key(ch):
            return
        if self.mode == "normal":
            self.df_mode.handle_key(ch)
            return
