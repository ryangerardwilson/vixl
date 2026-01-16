# ~/Apps/vixl/df_editor_df_mode.py
# df_editor_df_mode.py retains pandas import for isna usage
from pandas import isna
from cell_coercion import coerce_cell_value


class DfEditorDfMode:
    """Handles DF-normal key handling and leader sequences."""

    def __init__(
        self,
        ctx,
        counts,
        undo_mgr,
        external,
        df_ops,
        visual,
        show_leader_status_cb,
        leader_seq_cb,
        open_json_preview_cb,
    ):
        self.ctx = ctx
        self.counts = counts
        self.undo_mgr = undo_mgr
        self.external = external
        self.df_ops = df_ops
        self.visual = visual
        self._show_leader_status = show_leader_status_cb
        self._leader_seq = leader_seq_cb
        self._open_json_preview = open_json_preview_cb

    def handle_key(self, ch: int) -> bool:
        total_rows = len(self.ctx.state.df)
        total_cols = len(self.ctx.state.df.columns)

        # '.' repeat
        if ch == ord("."):
            return False  # let DfEditor handle repeat for now

        # numeric prefixes
        if ord("0") <= ch <= ord("9"):
            self.counts.push_digit(ch - ord("0"))
            return True

        if total_cols == 0:
            self.ctx.grid.curr_row = 0
            self.ctx.grid.curr_col = 0
            self.ctx.grid.row_offset = 0
            self.ctx.grid.col_offset = 0
            self.counts.reset()
            return True

        if total_rows == 0:
            self.ctx.grid.curr_row = 0
            self.ctx.grid.row_offset = 0

        # clamp cursor
        if self.ctx.grid.curr_row >= total_rows:
            self.ctx.grid.curr_row = total_rows - 1
        if self.ctx.grid.curr_col >= total_cols:
            self.ctx.grid.curr_col = total_cols - 1
        if self.ctx.grid.row_offset > self.ctx.grid.curr_row:
            self.ctx.grid.row_offset = self.ctx.grid.curr_row
        if self.ctx.grid.col_offset > self.ctx.grid.curr_col:
            self.ctx.grid.col_offset = self.ctx.grid.curr_col

        r, c = self.ctx.grid.curr_row, self.ctx.grid.curr_col
        col_name = self.ctx.state.df.columns[c]
        val = None if total_rows == 0 else self.ctx.state.df.iloc[r, c]
        base = "" if (val is None or isna(val)) else str(val)

        visible_rows = max(
            1, self.ctx.paginator.page_end - self.ctx.paginator.page_start
        )
        jump_rows = max(1, round(visible_rows * 0.05))
        jump_cols = max(1, round(max(1, total_cols) * 0.20))

        # 'n' enters cell_normal
        # leader state machine
        if self.ctx.df_leader_state:
            return self._handle_df_leader(ch, total_rows, total_cols, r, c, base)

        # visual toggle (Vim-style)
        if ch == ord("v"):
            self.visual.toggle()
            self.counts.reset()
            return True

        # regular navigation commands
        if ch == ord("u"):
            self.undo_mgr.undo()
            if getattr(self.visual, "exit", None):
                self.visual.exit()
            return True
        if ch == ord("r"):
            self.undo_mgr.redo()
            if getattr(self.visual, "exit", None):
                self.visual.exit()
            return True

        if ch == 10:  # Ctrl+J
            if total_rows > 0:
                step = max(1, jump_rows * self.counts.consume())
                target = min(total_rows - 1, self.ctx.grid.curr_row + step)
                self.ctx.paginator.ensure_row_visible(target)
                self.ctx.grid.row_offset = 0
                self.ctx.grid.curr_row = target
                self.visual.post_move()
            return True

        if ch == 11:  # Ctrl+K
            if total_rows > 0:
                step = max(1, jump_rows * self.counts.consume())
                target = max(0, self.ctx.grid.curr_row - step)
                self.ctx.paginator.ensure_row_visible(target)
                self.ctx.grid.row_offset = 0
                self.ctx.grid.curr_row = target
                self.visual.post_move()
            return True

        if ch == 8:  # Ctrl+H
            if total_cols > 0:
                step = max(1, jump_cols * self.counts.consume())
                target = max(0, self.ctx.grid.curr_col - step)
                self.ctx.grid.curr_col = target
                self.ctx.grid.adjust_col_viewport()
                self.visual.post_move()
            return True

        if ch == 12:  # Ctrl+L
            if total_cols > 0:
                step = max(1, jump_cols * self.counts.consume())
                target = min(total_cols - 1, self.ctx.grid.curr_col + step)
                self.ctx.grid.curr_col = target
                self.ctx.grid.adjust_col_viewport()
                self.visual.post_move()
            return True

        # normal vim movement
        count = self.counts.consume()
        if ch == ord("h"):
            target = max(0, self.ctx.grid.curr_col - count)
            self.ctx.grid.curr_col = target
            self.ctx.grid.adjust_col_viewport()
            self.visual.post_move()
            return True
        if ch == ord("l"):
            target = min(total_cols - 1, self.ctx.grid.curr_col + count)
            self.ctx.grid.curr_col = target
            self.ctx.grid.adjust_col_viewport()
            self.visual.post_move()
            return True
        if ch == ord("j") and total_rows > 0:
            target = min(total_rows - 1, self.ctx.grid.curr_row + count)
            self.ctx.paginator.ensure_row_visible(target)
            self.ctx.grid.row_offset = 0
            self.ctx.grid.curr_row = target
            self.visual.post_move()
            return True
        if ch == ord("k") and total_rows > 0:
            target = max(0, self.ctx.grid.curr_row - count)
            self.ctx.paginator.ensure_row_visible(target)
            self.ctx.grid.row_offset = 0
            self.ctx.grid.curr_row = target
            self.visual.post_move()
            return True

        # visual-mode actions
        if getattr(self.ctx, "visual_active", False):
            if ch == ord("d"):
                rect = self.visual.rect()
                if not rect:
                    self.visual.exit()
                    return True
                r0, r1, c0, c1 = rect
                if r1 < r0 or c1 < c0 or total_rows == 0 or total_cols == 0:
                    self.visual.exit()
                    return True
                self.undo_mgr.push_undo()
                try:
                    for cc in range(c0, c1 + 1):
                        col_name = self.ctx.state.df.columns[cc]
                        empty = coerce_cell_value(self.ctx.state.df, col_name, "")
                        for rr in range(r0, r1 + 1):
                            self.ctx.state.df.iloc[rr, cc] = empty
                    self.ctx.grid.df = self.ctx.state.df
                    self.ctx._set_status(
                        f"Cleared {(r1 - r0 + 1) * (c1 - c0 + 1)} cells", 2
                    )
                    self.undo_mgr.set_last_action("cell_clear")
                except Exception:
                    self.ctx._set_status("Clear failed", 3)
                self.visual.exit()
                self.counts.reset()
                return True
            if ch == ord("i"):
                rect = self.visual.rect()
                if not rect:
                    self.visual.exit()
                    return True
                self.external.queue_visual_fill(rect)
                return True
            if ch == 27:  # Esc exits visual
                self.visual.exit()
                self.counts.reset()
                return True

        if ch == ord("x"):
            if total_rows == 0 or total_cols == 0:
                return True
            self.undo_mgr.push_undo()
            r, c = self.ctx.grid.curr_row, self.ctx.grid.curr_col
            col_name = self.ctx.state.df.columns[c]
            try:
                self.ctx.state.df.iloc[r, c] = coerce_cell_value(
                    self.ctx.state.df, col_name, ""
                )
            except Exception:
                self.ctx.state.df.iloc[r, c] = ""
            self.ctx.grid.df = self.ctx.state.df
            self.ctx._set_status("Cell cleared", 2)
            self.undo_mgr.set_last_action("cell_clear")
            self.counts.reset()
            return True

        if ch == ord("i"):
            self.external.queue_external_edit()
            return True

        # leader entry
        if ch == ord(","):
            self.ctx.df_leader_state = "leader"
            self.counts.reset()
            self._show_leader_status(self._leader_seq("leader"))
            return True

        return False

    def _copy_selection_to_clipboard(self, cmd, rect):
        if not rect or cmd is None:
            return False
        r0, r1, c0, c1 = rect
        try:
            import subprocess

            sel_df = self.ctx.state.df.iloc[r0 : r1 + 1, c0 : c1 + 1]
            tsv_data = sel_df.to_csv(sep="\t", index=False)
            subprocess.run(cmd, input=tsv_data, text=True, check=True)
            self.ctx._set_status("Selection copied", 3)
            return True
        except FileNotFoundError:
            self.ctx._set_status("Clipboard command not found", 3)
        except Exception:
            self.ctx._set_status("Copy failed", 3)
        return False

    def _handle_df_leader(self, ch, total_rows, total_cols, r, c, base):
        state = self.ctx.df_leader_state
        self.ctx.df_leader_state = None

        if state == "leader":
            return self._handle_df_leader_root(ch, total_rows, total_cols, r, c, base)
        if state == "y":
            return self._handle_leader_y(ch, r, c)
        if state == "p":
            return self._handle_leader_p(ch, r, c)
        if state == "i":
            if ch == ord("c"):
                self.ctx.df_leader_state = "ic"
                self._show_leader_status(self._leader_seq("ic"))
                return True
            if ch == ord("r"):
                self.ctx.df_leader_state = "ir"
                self._show_leader_status(self._leader_seq("ir"))
                return True
            self._show_leader_status("")
            return True
        if state == "ic":
            if ch == ord("a"):
                self._show_leader_status(",ica")
                self.df_ops.start_insert_column(after=True)
                return True
            if ch == ord("b"):
                self._show_leader_status(",icb")
                self.df_ops.start_insert_column(after=False)
                return True
            self._show_leader_status("")
            return True
        if state == "ir":
            count = self.counts.consume()
            if ch == ord("a"):
                self._show_leader_status(",ira")
                self.df_ops.insert_rows(above=True, count=count)
                return True
            if ch == ord("b"):
                self._show_leader_status(",irb")
                self.df_ops.insert_rows(above=False, count=count)
                return True
            self._show_leader_status("")
            self.counts.reset()
            return True
        if state == "d":
            if ch == ord("r"):
                if total_rows == 0:
                    self.ctx._set_status("No rows", 3)
                    self.counts.reset()
                    return True
                count = self.counts.consume()
                self._show_leader_status(",dr")
                self.df_ops.delete_rows(count)
                return True
            if ch == ord("c"):
                self._show_leader_status(",dc")
                self.df_ops.delete_current_column()
                self.counts.reset()
                return True
            self._show_leader_status("")
            self.counts.reset()
            return True
        if state == "r":
            if ch == ord("n"):
                self.ctx.df_leader_state = "rn"
                self._show_leader_status(self._leader_seq("rn"))
                return True
            self._show_leader_status("")
            return True
        if state == "rn":
            if ch == ord("c"):
                self._show_leader_status(",rnc")
                self.df_ops.start_rename_column()
                return True
            self._show_leader_status("")
            return True
        if state == "x":
            if ch == ord("r"):
                self._show_leader_status(",xr")
                self.df_ops.toggle_row_expanded()
                return True
            if ch == ord("a"):
                self.ctx.df_leader_state = "xa"
                self._show_leader_status(self._leader_seq("xa"))
                return True
            if ch == ord("c"):
                self._show_leader_status(",xc")
                self.df_ops.collapse_all_rows()
                return True
            if ch == ord("+"):
                count = self.counts.consume()
                self._show_leader_status(",x+")
                self.df_ops.adjust_row_lines(count)
                return True
            if ch == ord("-"):
                count = self.counts.consume()
                self._show_leader_status(",x-")
                self.df_ops.adjust_row_lines(-count)
                return True
            self._show_leader_status("")
            self.counts.reset()
            return True
        if state == "xa":
            if ch == ord("r"):
                self._show_leader_status(",xar")
                self.df_ops.toggle_all_rows_expanded()
                return True
            self._show_leader_status("")
            self.counts.reset()
            return True

        self._show_leader_status("")
        return True

    def _handle_df_leader_root(self, ch, total_rows, total_cols, r, c, base):
        if ch == ord("y"):
            self.ctx.df_leader_state = "y"
            self._show_leader_status(",y")
            return True
        if ch == ord("p"):
            self.ctx.df_leader_state = "p"
            self._show_leader_status(",p")
            return True
        if ch == ord("j"):
            if total_rows == 0:
                self.counts.reset()
                return True
            target = total_rows - 1
            self.ctx.paginator.ensure_row_visible(target)
            self.ctx.grid.row_offset = 0
            self.ctx.grid.curr_row = target
            self.ctx.grid.highlight_mode = "cell"
            self.visual.post_move()
            self.counts.reset()
            return True
        if ch == ord("k"):
            if total_rows == 0:
                self.counts.reset()
                return True
            self.ctx.paginator.ensure_row_visible(0)
            self.ctx.grid.row_offset = 0
            self.ctx.grid.curr_row = 0
            self.ctx.grid.highlight_mode = "cell"
            self.visual.post_move()
            self.counts.reset()
            return True
        if ch == ord("h"):
            if total_cols == 0:
                self.counts.reset()
                return True
            self.ctx.grid.curr_col = 0
            self.ctx.grid.adjust_col_viewport()
            self.visual.post_move()
            self.counts.reset()
            return True
        if ch == ord("l"):
            if total_cols == 0:
                self.counts.reset()
                return True
            self.ctx.grid.curr_col = total_cols - 1
            self.ctx.grid.adjust_col_viewport()
            self.visual.post_move()
            self.counts.reset()
            return True
        if ch == ord("x"):
            self.ctx.df_leader_state = "x"
            self._show_leader_status(self._leader_seq("x"))
            return True
        if ch == ord("i"):
            self.ctx.df_leader_state = "i"
            self._show_leader_status(self._leader_seq("i"))
            return True
        if ch == ord("d"):
            self.ctx.df_leader_state = "d"
            self._show_leader_status(self._leader_seq("d"))
            return True
        if ch == ord("r"):
            self.ctx.df_leader_state = "r"
            self._show_leader_status(self._leader_seq("r"))
            return True
        self._show_leader_status("")
        return True

    def _handle_leader_y(self, ch, r, c):
        if ch == ord("a"):
            cmd = None
            if getattr(self.ctx, "config", None):
                cmd = self.ctx.config.get("CLIPBOARD_INTERFACE_COMMAND")
            if not cmd:
                self.ctx._set_status("Clipboard not configured", 3)
                self.counts.reset()
                return True
            try:
                import subprocess

                tsv_data = self.ctx.state.df.to_csv(sep="\t", index=False)
                subprocess.run(cmd, input=tsv_data, text=True, check=True)
                self.ctx._set_status("DF copied", 3)
            except FileNotFoundError:
                self.ctx._set_status("Clipboard command not found", 3)
            except Exception:
                self.ctx._set_status("Copy failed", 3)
            self.counts.reset()
            return True
        if ch == ord("c"):
            cmd = None
            if getattr(self.ctx, "config", None):
                cmd = self.ctx.config.get("CLIPBOARD_INTERFACE_COMMAND")
            if not cmd:
                self.ctx._set_status("Clipboard not configured", 3)
                self.counts.reset()
                return True

            # Visual selection copy
            if getattr(self.ctx, "visual_active", False) and self.visual:
                rect = self.visual.rect()
                if rect and self._copy_selection_to_clipboard(cmd, rect):
                    self.counts.reset()
                    return True

            try:
                import subprocess

                value = self.ctx.state.df.iloc[r, c]
                value = "" if (value is None or isna(value)) else str(value)
                subprocess.run(cmd, input=value, text=True, check=True)
                self.ctx._set_status("Cell copied", 3)
            except FileNotFoundError:
                self.ctx._set_status("Clipboard command not found", 3)
            except Exception:
                self.ctx._set_status("Copy failed", 3)
            self.counts.reset()
            return True
        self.counts.reset()
        return True

    def _handle_leader_p(self, ch, r, c):
        if ch == ord("j"):
            self._open_json_preview(r, c)
            self.counts.reset()
            return True
        self.counts.reset()
        return True
