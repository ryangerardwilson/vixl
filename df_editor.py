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
        self.mode = 'normal'  # normal | cell_normal | cell_insert
        self.cell_buffer = ""
        self.cell_cursor = 0
        self.cell_hscroll = 0
        self.cell_col = None
        self.cell_leader_state = None  # None | 'leader' | 'c' | 'd' | 'n'
        self.df_leader_state = None   # None | 'leader'

    # ---------- helpers ---------- 
    # (unchanged - _coerce_cell_value, _autoscroll_insert)

    # ---------- public API ----------
    def handle_key(self, ch):
        # ---------- cell insert mode ----------
        if self.mode == 'cell_insert':
            # ... (all insert mode logic unchanged) ...
            return

        # ---------- cell normal mode ----------
        if self.mode == 'cell_normal':
            # ... (all cell_normal logic unchanged) ...
            return

        # ---------- df normal (hover) mode ----------
        if self.mode == 'normal':
            total_rows = len(self.state.df)
            total_cols = len(self.state.df.columns)

            if total_rows == 0 or total_cols == 0:
                self.grid.curr_row = 0
                self.grid.curr_col = 0
                self.grid.row_offset = 0
                self.grid.col_offset = 0
                return

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
            base = '' if (val is None or pd.isna(val)) else str(val)

            visible_rows = max(1, self.paginator.page_end - self.paginator.page_start)
            jump_rows = max(1, round(visible_rows * 0.05))
            jump_cols = max(1, round(max(1, total_cols) * 0.20))

            # Leader sequences
            if self.df_leader_state:
                state = self.df_leader_state
                self.df_leader_state = None
                if state == 'leader':
                    if ch == ord('y'):
                        try:
                            import subprocess
                            tsv_data = self.state.df.to_csv(sep='\t', index=False)
                            subprocess.run(['wl-copy'], input=tsv_data, text=True, check=True)
                            self._set_status("DF copied", 3)
                        except Exception:
                            self._set_status("Copy failed", 3)
                        return
                    if ch == ord('j'):
                        if total_rows == 0: return
                        target = total_rows - 1
                        self.paginator.ensure_row_visible(target)
                        self.grid.row_offset = 0
                        self.grid.curr_row = target
                        self.grid.highlight_mode = 'cell'
                        return
                    if ch == ord('k'):
                        if total_rows == 0: return
                        self.paginator.ensure_row_visible(0)
                        self.grid.row_offset = 0
                        self.grid.curr_row = 0
                        self.grid.highlight_mode = 'cell'
                        return
                    if ch == ord('h'):
                        if total_cols == 0: return
                        self.grid.curr_col = 0
                        return
                    if ch == ord('l'):
                        if total_cols == 0: return
                        self.grid.curr_col = total_cols - 1
                        # ───────────────────────────────────────────────────────────────
                        # FIXED: Removed the line below that broke right-scrolling
                        # if self.grid.col_offset > target:
                        #     self.grid.col_offset = target
                        # Now draw() will correctly scroll to show the last columns
                        # ───────────────────────────────────────────────────────────────
                        return

            if self.cell_leader_state:
                # ... (cell leader logic unchanged) ...
                return

            if ch == ord(','):
                self.df_leader_state = 'leader'
                self.cell_leader_state = None
                return

            if ch == ord('i'):
                # ... (enter insert unchanged) ...
                return

            if ch == 10:   # Ctrl+J
                if total_rows > 0:
                    target = min(total_rows - 1, self.grid.curr_row + jump_rows)
                    self.paginator.ensure_row_visible(target)
                    self.grid.row_offset = 0
                    self.grid.curr_row = target
                return

            if ch == 11:   # Ctrl+K
                if total_rows > 0:
                    target = max(0, self.grid.curr_row - jump_rows)
                    self.paginator.ensure_row_visible(target)
                    self.grid.row_offset = 0
                    self.grid.curr_row = target
                return

            if ch == 8:   # Ctrl+H  ← jump left
                if total_cols > 0:
                    target = max(0, self.grid.curr_col - jump_cols)
                    self.grid.curr_col = target
                    # No forced col_offset change - let draw() handle it
                return

            if ch == 12:  # Ctrl+L  ← jump right  ← THIS WAS ALSO CRASHING
                if total_cols > 0:
                    target = min(total_cols - 1, self.grid.curr_col + jump_cols)
                    self.grid.curr_col = target
                    # ───────────────────────────────────────────────────────────────
                    # FIXED: Removed problematic line
                    # if self.grid.col_offset > target:
                    #     self.grid.col_offset = target
                    # ───────────────────────────────────────────────────────────────
                return

            if ch == ord('h'):
                self.grid.move_left()
            elif ch == ord('l'):
                self.grid.move_right()
            elif ch == ord('j'):
                if self.grid.curr_row + 1 >= self.paginator.page_end:
                    if self.paginator.page_end < self.paginator.total_rows:
                        self.paginator.next_page()
                        self.grid.row_offset = 0
                        self.grid.curr_row = self.paginator.page_start
                    else:
                        self.grid.curr_row = max(0, self.paginator.total_rows - 1)
                else:
                    self.grid.move_down()
            elif ch == ord('k'):
                if self.grid.curr_row - 1 < self.paginator.page_start:
                    if self.paginator.page_index > 0:
                        self.paginator.prev_page()
                        self.grid.row_offset = 0
                        self.grid.curr_row = max(self.paginator.page_start, self.paginator.page_end - 1)
                    else:
                        self.grid.curr_row = 0
                else:
                    self.grid.move_up()

            elif ch == ord('J'):
                self.grid.move_row_down()
            elif ch == ord('K'):
                self.grid.move_row_up()
            elif ch == ord('H'):
                self.grid.move_col_left()
            elif ch == ord('L'):
                self.grid.move_col_right()
            return
