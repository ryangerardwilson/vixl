import curses


class GridPane:
    def __init__(self, df):
        self.df = df
        self.curr_row = 0
        self.curr_col = 0
        self.row_offset = 0
        self.col_offset = 0
        self.highlight_mode = 'cell'  # cell | row | column

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
    def draw(self, win, active=False):
        win.erase()
        h, w = win.getmaxyx()
        CELL_W = 12
        col_w = CELL_W + 1

        max_rows = h - 3
        max_cols = max(1, (w - 4) // col_w)

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
            name = str(self.df.columns[c])[:CELL_W].rjust(CELL_W)
            win.addnstr(1, x, name, CELL_W, curses.A_BOLD)
            x += col_w

        # rows
        y = 2
        for r in visible_rows:
            win.addnstr(y, 0, str(r).rjust(3), 3)
            x = 4
            for c in visible_cols:
                val = self.df.iloc[r, c]
                text = '' if val is None else str(val)
                cell = text[:CELL_W].rjust(CELL_W)

                attr = 0
                if self.highlight_mode == 'row' and r == self.curr_row:
                    attr = curses.A_REVERSE
                elif self.highlight_mode == 'column' and c == self.curr_col:
                    attr = curses.A_REVERSE
                elif self.highlight_mode == 'cell' and r == self.curr_row and c == self.curr_col:
                    attr = curses.A_REVERSE

                win.addnstr(y, x, cell, CELL_W, attr)
                x += col_w
            y += 1
            if y >= h - 1:
                break

        if active:
            win.addnstr(h - 2, w - 8, " DF ", 6)
        win.box()
        win.refresh()