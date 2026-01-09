import curses


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
    ):
        win.erase()
        h, w = win.getmaxyx()

        # compute column widths
        widths = []
        for col in self.df.columns:
            max_len = len(str(col))
            for v in self.df[col]:
                s = '' if v is None else str(v)
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
        if self.curr_row < self.row_offset:
            self.row_offset = self.curr_row
        elif self.curr_row >= self.row_offset + max_rows:
            self.row_offset = self.curr_row - max_rows + 1

        if self.curr_col < self.col_offset:
            self.col_offset = self.curr_col
        elif self.curr_col >= self.col_offset + max_cols:
            self.col_offset = self.curr_col - max_cols + 1

        visible_rows = range(self.row_offset, min(len(self.df), self.row_offset + max_rows))
        visible_cols = range(self.col_offset, min(len(self.df.columns), self.col_offset + max_cols))

        # header
        x = 4
        for c in visible_cols:
            cw = widths[c]
            name = str(self.df.columns[c])[:cw].rjust(cw)
            win.addnstr(1, x, name, cw, curses.A_BOLD)
            x += cw + 1

        # rows
        y = 2
        for r in visible_rows:
            win.addnstr(y, 0, str(r).rjust(3), 3)
            x = 4
            for c in visible_cols:
                cw = widths[c]

                # base text
                if editing and r == edit_row and c == edit_col:
                    text = edit_buffer or ''
                else:
                    val = self.df.iloc[r, c]
                    text = '' if val is None else str(val)

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

                # cursor rendering
                if editing and r == edit_row and c == edit_col and edit_cursor is not None:
                    buf_len = len(text)
                    visible_len = min(buf_len - edit_hscroll, cw)
                    text_start_x = x + (cw - visible_len)

                    if insert_mode:
                        gap = max(0, min(edit_cursor - edit_hscroll, visible_len))
                        cx = text_start_x + gap
                        cx = max(x, min(x + cw - 1, cx))
                        win.addnstr(y, cx, ' ', 1, curses.A_REVERSE)
                    else:
                        if buf_len > 0 and visible_len > 0:
                            char_index = max(0, min(visible_len - 1, edit_cursor - edit_hscroll - 1))
                            cx = text_start_x + char_index
                            cx = max(x, min(x + cw - 1, cx))
                            win.addnstr(y, cx, visible[char_index], 1, curses.A_REVERSE)

                x += cw + 1
            y += 1
            if y >= h - 1:
                break

        if active:
            win.addnstr(h - 2, w - 8, ' DF ', 6)
        win.refresh()