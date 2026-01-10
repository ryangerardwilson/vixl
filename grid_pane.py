# ~/Apps/vixl/grid_pane.py
import curses
import pandas as pd


class GridPane:
    PAIR_CELL_ACTIVE = 1
    PAIR_CURSOR_INSERT = 2
    PAIR_CURSOR_NORMAL_BG = 3
    PAIR_CURSOR_NORMAL_CHAR = 4
    PAIR_CELL_ACTIVE_TEXT = 5
    MAX_COL_WIDTH = 40

    def __init__(self, df):
        self.df = df
        try:
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(self.PAIR_CELL_ACTIVE, -1, curses.COLOR_WHITE)
            curses.init_pair(self.PAIR_CURSOR_INSERT, curses.COLOR_BLACK, curses.COLOR_WHITE)
            curses.init_pair(self.PAIR_CURSOR_NORMAL_BG, curses.COLOR_BLACK, curses.COLOR_BLACK)
            curses.init_pair(self.PAIR_CURSOR_NORMAL_CHAR, curses.COLOR_WHITE, curses.COLOR_BLACK)
            curses.init_pair(self.PAIR_CELL_ACTIVE_TEXT, curses.COLOR_BLACK, curses.COLOR_WHITE)
        except curses.error:
            pass

        self.curr_row = 0
        self.curr_col = 0
        self.row_offset = 0
        self.col_offset = 0
        self.highlight_mode = 'cell'

    def get_col_width(self, col_idx):
        if col_idx < 0 or col_idx >= len(self.df.columns):
            return self.MAX_COL_WIDTH
        col = self.df.columns[col_idx]
        max_len = len(str(col))
        for v in self.df[col]:
            if v is None or pd.isna(v):
                s = ''
            else:
                s = str(v)
            max_len = max(max_len, len(s))
        return min(self.MAX_COL_WIDTH, max_len + 2)

    # ---------- navigation ----------
    def move_left(self):
        self.curr_col = max(0, self.curr_col - 1)
        self.highlight_mode = 'cell'

    def move_right(self):
        self.curr_col = min(len(self.df.columns) - 1, self.curr_col + 1)
        self.highlight_mode = 'cell'

    def move_down(self):
        self.curr_row = min(len(self.df) - 1, self.curr_row + 1)
        self.highlight_mode = 'cell'

    def move_up(self):
        self.curr_row = max(0, self.curr_row - 1)
        self.highlight_mode = 'cell'

    def move_row_down(self):
        self.curr_row = min(len(self.df) - 1, self.curr_row + 1)
        self.highlight_mode = 'row'

    def move_row_up(self):
        self.curr_row = max(0, self.curr_row - 1)
        self.highlight_mode = 'row'

    def move_col_left(self):
        self.curr_col = max(0, self.curr_col - 1)
        self.highlight_mode = 'column'

    def move_col_right(self):
        self.curr_col = min(len(self.df.columns) - 1, self.curr_col + 1)
        self.highlight_mode = 'column'

    # ---------- rendering ----------
    def draw(
        self,
        win,
        active=False,
        editing=False,
        insert_mode=False,
        edit_row=None,
        edit_col=None,
        edit_buffer=None,
        edit_cursor=None,
        edit_hscroll=0,
        page_start=0,
        page_end=None,
    ):
        win.erase()
        h, w = win.getmaxyx()

        if page_end is None:
            page_end = len(self.df)
        total_rows = max(0, page_end - page_start)

        # compute column widths using only the page slice
        widths = []
        df_slice = self.df.iloc[page_start:page_end]
        for col in df_slice.columns:
            max_len = len(str(col))
            for v in df_slice[col]:
                s = '' if (v is None or pd.isna(v)) else str(v)
                max_len = max(max_len, len(s))
            widths.append(min(self.MAX_COL_WIDTH, max_len + 2))

        max_rows = h - 3
        avail_w = w - 4

        max_cols = 0
        used = 0
        for cw in widths[self.col_offset:]:
            if used + cw + 1 > avail_w:
                break
            used += cw + 1
            max_cols += 1
        max_cols = max(1, max_cols)

        # adjust viewport
        local_curr = self.curr_row - page_start
        if local_curr < 0:
            local_curr = 0
        if local_curr >= total_rows:
            local_curr = max(0, total_rows - 1)
            self.curr_row = page_start + local_curr

        max_row_offset = max(0, total_rows - max_rows)
        if self.row_offset > max_row_offset:
            self.row_offset = max_row_offset

        if local_curr < self.row_offset:
            self.row_offset = local_curr
        elif local_curr >= self.row_offset + max_rows:
            self.row_offset = local_curr - max_rows + 1

        if self.curr_col < self.col_offset:
            self.col_offset = self.curr_col
        elif self.curr_col >= self.col_offset + max_cols:
            self.col_offset = self.curr_col - max_cols + 1


        visible_rows = range(
            page_start + self.row_offset,
            min(page_end, page_start + self.row_offset + max_rows),
        )
        visible_cols = range(self.col_offset, min(len(df_slice.columns), self.col_offset + max_cols))

        # header
        x = 4
        for c in visible_cols:
            cw = widths[c]
            name = str(df_slice.columns[c])[:cw].rjust(cw)
            win.addnstr(1, x, name, cw, curses.A_BOLD)
            x += cw + 1

        # rows
        y = 2
        for r in visible_rows:
            win.addnstr(y, 0, str(r).rjust(3), 3)
            x = 4
            local_r = r - page_start
            for c in visible_cols:
                cw = widths[c]

                # base text
                if editing and r == edit_row and c == edit_col:
                    text = edit_buffer or ''
                else:
                    val = self.df.iloc[r, c]
                    text = '' if (val is None or pd.isna(val)) else str(val)

                # horizontal scroll for edited cell
                if editing and r == edit_row and c == edit_col:
                    visible = text[edit_hscroll: edit_hscroll + cw]
                else:
                    visible = text[:cw]

                cell = visible.rjust(cw)

                attr = 0
                if not editing:
                    active_cell = (
                        (self.highlight_mode == 'row' and r == self.curr_row)
                        or (self.highlight_mode == 'column' and c == self.curr_col)
                        or (self.highlight_mode == 'cell' and r == self.curr_row and c == self.curr_col)
                    )
                    if active_cell:
                        attr = curses.color_pair(self.PAIR_CELL_ACTIVE_TEXT)

                win.addnstr(y, x, cell, cw, attr)

                # === FINAL CURSOR RENDERING - PERFECT ALIGNMENT FOR BOTH MODES ===
                if editing and r == edit_row and c == edit_col and edit_cursor is not None:
                    visible_len = len(visible)
                    text_start_x = x + (cw - visible_len)  # padding from rjust

                    relative_pos = edit_cursor - edit_hscroll

                    if insert_mode:
                        # Thin insert cursor - can be at end
                        pos = max(0, min(relative_pos, visible_len))
                        cx = text_start_x + pos
                        cx = max(x, min(x + cw - 1, cx))
                        win.addnstr(y, cx, ' ', 1, curses.A_REVERSE)
                    else:
                        # Normal mode block cursor - identical positioning to insert
                        pos = max(0, min(relative_pos, visible_len))
                        cx = text_start_x + pos
                        cx = max(x, min(x + cw - 1, cx))
                        if pos < visible_len:
                            ch = visible[pos]
                            win.addch(y, cx, ch, curses.A_REVERSE)
                        else:
                            # At absolute end: reverse space (consistent with insert)
                            win.addnstr(y, cx, ' ', 1, curses.A_REVERSE)

                x += cw + 1
            y += 1
            if y >= h - 1:
                break

        win.refresh()
