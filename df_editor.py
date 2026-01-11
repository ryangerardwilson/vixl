# ~/Apps/vixl/df_editor.py
import curses
import pandas as pd


class DfEditor:
    """Handles dataframe editing state and key interactions."""

    def __init__(self, state, grid, paginator, set_status_cb):
        self.state = state
        self.grid = grid
        self.paginator = paginator
        self._set_status = set_status_cb

        # DF cell editing state
        self.mode = "normal"  # normal | cell_normal | cell_insert
        self.cell_buffer = ""
        self.cell_cursor = 0
        self.cell_hscroll = 0
        self.cell_col = None
        self.cell_leader_state = None  # None | 'leader' | 'c' | 'd' | 'n'
        self.df_leader_state = None  # None | 'leader'

    # ---------- helpers ----------
    def _coerce_cell_value(self, col, text):
        dtype = self.state.df[col].dtype
        if pd.api.types.is_integer_dtype(dtype):
            return int(text) if text != "" else None
        if pd.api.types.is_float_dtype(dtype):
            return float(text) if text != "" else None
        if pd.api.types.is_bool_dtype(dtype):
            return text.lower() in ("1", "true", "yes")
        return text

    def _autoscroll_insert(self):
        cw = self.grid.get_col_width(self.grid.curr_col)
        if self.cell_cursor < self.cell_hscroll:
            self.cell_hscroll = self.cell_cursor
        elif self.cell_cursor > self.cell_hscroll + cw - 1:
            self.cell_hscroll = self.cell_cursor - (cw - 1)

        max_scroll = (
            max(0, len(self.cell_buffer) - cw + 1) if len(self.cell_buffer) >= cw else 0
        )
        self.cell_hscroll = max(0, min(self.cell_hscroll, max_scroll))

    # ---------- public API ----------
    def handle_key(self, ch):
        # ---------- cell insert ----------
        if self.mode == "cell_insert":
            if ch == 27:  # Esc
                self.cell_buffer = self.cell_buffer.strip()

                r, c = self.grid.curr_row, self.grid.curr_col
                col = self.cell_col
                try:
                    val = self._coerce_cell_value(col, self.cell_buffer)
                    self.state.df.iloc[r, c] = val
                except Exception:
                    self._set_status(f"Invalid value for column '{col}'", 3)

                # Clean reset for normal mode
                self.cell_cursor = 0
                self.cell_hscroll = 0
                self.mode = "cell_normal"

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
            if self.cell_leader_state:
                state = self.cell_leader_state
                self.cell_leader_state = None

                if state == "leader":
                    if ch == ord("e"):
                        if not self.cell_buffer.endswith(" "):
                            self.cell_buffer += " "
                        self.cell_cursor = len(self.cell_buffer) - 1
                        self.mode = "cell_insert"
                        return
                    if ch == ord("c"):
                        self.cell_leader_state = "c"
                        return
                    if ch == ord("d"):
                        self.cell_leader_state = "d"
                        return
                    if ch == ord("n"):
                        self.cell_leader_state = "n"
                        return
                    return

                if state == "c" and ch == ord("c"):
                    self.cell_buffer = ""
                    self.cell_cursor = 0
                    self.cell_hscroll = 0
                    self.mode = "cell_insert"
                    return

                if state == "d" and ch == ord("c"):
                    self.cell_buffer = ""
                    self.cell_cursor = 0
                    self.cell_hscroll = 0
                    return

                if state == "n" and ch == ord("r"):
                    # only allow row insertion while in df normal (hover) mode
                    if self.mode != "normal":
                        return
                    row = self.state.build_default_row()
                    insert_at = self.grid.curr_row + 1 if len(self.state.df) > 0 else 0
                    new_row = pd.DataFrame([row], columns=self.state.df.columns)
                    self.state.df = pd.concat(
                        [
                            self.state.df.iloc[:insert_at],
                            new_row,
                            self.state.df.iloc[insert_at:],
                        ],
                        ignore_index=True,
                    )
                    self.grid.df = self.state.df
                    self.paginator.update_total_rows(len(self.state.df))
                    self.paginator.ensure_row_visible(insert_at)
                    self.grid.curr_row = insert_at
                    self.grid.highlight_mode = "cell"
                    return

            if ch == ord(","):
                self.cell_leader_state = "leader"
                return

            buf_len = len(self.cell_buffer)
            cw = self.grid.get_col_width(self.grid.curr_col)

            moved = False
            if ch == ord("h"):
                if self.cell_cursor > 0:
                    self.cell_cursor -= 1
                    moved = True
            elif ch == ord("l"):
                if self.cell_cursor < buf_len:
                    self.cell_cursor += 1
                    moved = True

            if moved:
                if self.cell_cursor < self.cell_hscroll:
                    self.cell_hscroll = self.cell_cursor
                elif self.cell_cursor >= self.cell_hscroll + cw:
                    self.cell_hscroll = self.cell_cursor - cw + 1

                max_scroll = max(0, buf_len - cw + 1) if buf_len >= cw else 0
                self.cell_hscroll = max(0, min(self.cell_hscroll, max_scroll))
                return

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

            if total_rows == 0 or total_cols == 0:
                self.grid.curr_row = 0
                self.grid.curr_col = 0
                self.grid.row_offset = 0
                self.grid.col_offset = 0
                return

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
            val = self.state.df.iloc[r, c]
            base = "" if (val is None or pd.isna(val)) else str(val)

            visible_rows = max(1, self.paginator.page_end - self.paginator.page_start)
            jump_rows = max(1, round(visible_rows * 0.05))
            jump_cols = max(1, round(max(1, total_cols) * 0.20))

            if self.df_leader_state:
                state = self.df_leader_state
                self.df_leader_state = None

                if state == "leader":
                    if ch == ord("y"):
                        try:
                            import subprocess

                            tsv_data = self.state.df.to_csv(sep="\t", index=False)
                            subprocess.run(
                                ["wl-copy"], input=tsv_data, text=True, check=True
                            )
                            self._set_status("DF copied", 3)
                        except Exception:
                            self._set_status("Copy failed", 3)
                        return

                    if ch == ord("j"):
                        if total_rows == 0:
                            return
                        target = total_rows - 1
                        self.paginator.ensure_row_visible(target)
                        self.grid.row_offset = 0
                        self.grid.curr_row = target
                        self.grid.highlight_mode = "cell"
                        return

                    if ch == ord("k"):
                        if total_rows == 0:
                            return
                        self.paginator.ensure_row_visible(0)
                        self.grid.row_offset = 0
                        self.grid.curr_row = 0
                        self.grid.highlight_mode = "cell"
                        return

                    if ch == ord("h"):
                        if total_cols == 0:
                            return
                        self.grid.curr_col = 0
                        self.grid.adjust_col_viewport()
                        return

                    if ch == ord("l"):
                        if total_cols == 0:
                            return
                        self.grid.curr_col = total_cols - 1
                        self.grid.adjust_col_viewport()
                        return

            if self.cell_leader_state:
                state = self.cell_leader_state
                self.cell_leader_state = None

                if state == "leader":
                    if ch == ord("e"):
                        self.cell_col = col
                        self.cell_buffer = base
                        if not self.cell_buffer.endswith(" "):
                            self.cell_buffer += " "
                        self.cell_cursor = len(self.cell_buffer) - 1
                        self.mode = "cell_insert"
                        return
                    if ch == ord("c"):
                        self.cell_leader_state = "c"
                        return
                    if ch == ord("d"):
                        self.cell_leader_state = "d"
                        return
                    if ch == ord("n"):
                        self.cell_leader_state = "n"
                        return
                    return

                if state == "c" and ch == ord("c"):
                    self.cell_col = col
                    self.cell_buffer = ""
                    self.cell_cursor = 0
                    self.cell_hscroll = 0
                    self.mode = "cell_insert"
                    return

                if state == "d" and ch == ord("c"):
                    try:
                        self.state.df.iloc[r, c] = self._coerce_cell_value(col, "")
                    except Exception:
                        self.state.df.iloc[r, c] = ""
                    return

                if state == "n" and ch == ord("r"):
                    if self.mode != "normal":
                        return
                    row = self.state.build_default_row()
                    insert_at = self.grid.curr_row + 1 if len(self.state.df) > 0 else 0
                    new_row = pd.DataFrame([row], columns=self.state.df.columns)
                    self.state.df = pd.concat(
                        [
                            self.state.df.iloc[:insert_at],
                            new_row,
                            self.state.df.iloc[insert_at:],
                        ],
                        ignore_index=True,
                    )
                    self.grid.df = self.state.df
                    self.paginator.update_total_rows(len(self.state.df))
                    self.paginator.ensure_row_visible(insert_at)
                    self.grid.curr_row = insert_at
                    self.grid.highlight_mode = "cell"
                    return

            if ch == ord(","):
                self.df_leader_state = "leader"
                self.cell_leader_state = None
                return

            if ch == ord("i"):
                self.cell_col = col
                self.cell_buffer = base
                if not self.cell_buffer.endswith(" "):
                    self.cell_buffer += " "
                self.cell_cursor = len(self.cell_buffer) - 1
                self.mode = "cell_insert"
                return

            # Big jumps
            if ch == 10:  # Ctrl+J - down
                if total_rows > 0:
                    target = min(total_rows - 1, self.grid.curr_row + jump_rows)
                    self.paginator.ensure_row_visible(target)
                    self.grid.row_offset = 0
                    self.grid.curr_row = target
                return

            if ch == 11:  # Ctrl+K - up
                if total_rows > 0:
                    target = max(0, self.grid.curr_row - jump_rows)
                    self.paginator.ensure_row_visible(target)
                    self.grid.row_offset = 0
                    self.grid.curr_row = target
                return

            if ch == 8:  # Ctrl+H - left jump
                if total_cols > 0:
                    target = max(0, self.grid.curr_col - jump_cols)
                    self.grid.curr_col = target
                    self.grid.adjust_col_viewport()
                return

            if ch == 12:  # Ctrl+L - right jump
                if total_cols > 0:
                    target = min(total_cols - 1, self.grid.curr_col + jump_cols)
                    self.grid.curr_col = target
                    self.grid.adjust_col_viewport()
                return

            # Normal vim movement
            if ch == ord("h"):
                self.grid.move_left()
            elif ch == ord("l"):
                self.grid.move_right()
            elif ch == ord("j"):
                if self.grid.curr_row + 1 >= self.paginator.page_end:
                    if self.paginator.page_end < self.paginator.total_rows:
                        self.paginator.next_page()
                        self.grid.row_offset = 0
                        self.grid.curr_row = self.paginator.page_start
                    else:
                        self.grid.curr_row = max(0, self.paginator.total_rows - 1)
                else:
                    self.grid.move_down()
            elif ch == ord("k"):
                if self.grid.curr_row - 1 < self.paginator.page_start:
                    if self.paginator.page_index > 0:
                        self.paginator.prev_page()
                        self.grid.row_offset = 0
                        self.grid.curr_row = max(
                            self.paginator.page_start, self.paginator.page_end - 1
                        )
                    else:
                        self.grid.curr_row = 0
                else:
                    self.grid.move_up()

            elif ch == ord("J"):
                self.grid.move_row_down()
            elif ch == ord("K"):
                self.grid.move_row_up()
            elif ch == ord("H"):
                self.grid.move_col_left()
            elif ch == ord("L"):
                self.grid.move_col_right()

            return
