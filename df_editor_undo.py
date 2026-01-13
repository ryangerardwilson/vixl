class DfEditorUndo:
    """Manages undo/redo stacks and last-action tracking for DfEditor."""

    def __init__(self, ctx, counts):
        self.ctx = ctx
        self.counts = counts

    # ---------- snapshots ----------
    def snapshot_state(self):
        return {
            "df": self.ctx.state.df.copy(deep=True),
            "curr_row": self.ctx.grid.curr_row,
            "curr_col": self.ctx.grid.curr_col,
            "row_offset": self.ctx.grid.row_offset,
            "col_offset": self.ctx.grid.col_offset,
            "highlight_mode": self.ctx.grid.highlight_mode,
        }

    def restore_state(self, snap):
        self.ctx.state.df = snap["df"]
        self.ctx.grid.df = self.ctx.state.df
        self.ctx.grid.highlight_mode = snap.get("highlight_mode", "cell")
        self.ctx.paginator.update_total_rows(len(self.ctx.state.df))
        self.ctx.grid.curr_row = min(
            max(0, snap.get("curr_row", 0)), max(0, len(self.ctx.state.df) - 1)
        )
        self.ctx.grid.curr_col = min(
            max(0, snap.get("curr_col", 0)),
            max(0, len(self.ctx.state.df.columns) - 1),
        )
        self.ctx.grid.row_offset = max(0, snap.get("row_offset", 0))
        self.ctx.grid.col_offset = max(0, snap.get("col_offset", 0))
        self.ctx.paginator.ensure_row_visible(self.ctx.grid.curr_row)
        self.ctx.grid.highlight_mode = "cell"
        self.ctx.mode = "normal"
        self.ctx.cell_buffer = ""
        self.ctx.cell_cursor = 0
        self.ctx.cell_hscroll = 0
        self.ctx.pending_count = None

    # ---------- stack helpers ----------
    def push_undo(self):
        if not hasattr(self.ctx.state, "undo_stack"):
            return
        snap = self.snapshot_state()
        self.ctx.state.undo_stack.append(snap)
        if len(self.ctx.state.undo_stack) > getattr(self.ctx.state, "undo_max_depth", 50):
            self.ctx.state.undo_stack.pop(0)
        if hasattr(self.ctx.state, "redo_stack"):
            self.ctx.state.redo_stack.clear()

    def push_redo(self):
        if hasattr(self.ctx.state, "redo_stack"):
            self.ctx.state.redo_stack.append(self.snapshot_state())

    # ---------- undo/redo ----------
    def undo(self):
        stack = getattr(self.ctx.state, "undo_stack", None)
        if not stack:
            self.ctx._set_status("Nothing to undo", 2)
            self.counts.reset()
            return
        current = self.snapshot_state()
        self.push_redo()
        snap = stack.pop()
        self.restore_state(snap)
        remaining = len(stack)
        self.ctx._set_status(
            f"Undone ({remaining} more)" if remaining else "Undone", 2
        )
        self.ctx.pending_count = None

    def redo(self):
        redo_stack = getattr(self.ctx.state, "redo_stack", None)
        if not redo_stack:
            self.ctx._set_status("Nothing to redo", 2)
            self.counts.reset()
            return
        current = self.snapshot_state()
        undo_stack = getattr(self.ctx.state, "undo_stack", None)
        if undo_stack is not None:
            undo_stack.append(current)
            if len(undo_stack) > getattr(self.ctx.state, "undo_max_depth", 50):
                undo_stack.pop(0)
        snap = redo_stack.pop()
        self.restore_state(snap)
        remaining = len(redo_stack)
        self.ctx._set_status(
            f"Redone ({remaining} more)" if remaining else "Redone", 2
        )
        self.ctx.pending_count = None

    # ---------- last action ----------
    def reset_last_action(self):
        self.ctx.last_action = None

    def set_last_action(self, action_type: str, **kwargs):
        self.ctx.last_action = {"type": action_type, **kwargs}
