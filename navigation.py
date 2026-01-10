class NavigationController:
    def __init__(self, grid, pager):
        self.grid = grid
        self.pager = pager

    def _ensure_row_in_page(self):
        # Clamp current row within current page window
        if self.grid.curr_row < self.pager.page_start:
            self.grid.curr_row = self.pager.page_start
        if self.grid.curr_row >= self.pager.page_end:
            self.grid.curr_row = max(self.pager.page_start, self.pager.page_end - 1)

    def move_left(self):
        self.grid.move_left()

    def move_right(self):
        self.grid.move_right()

    def move_down(self):
        if self.grid.curr_row + 1 >= self.pager.page_end:
            if self.pager.page_end < self.pager.total_rows:
                self.pager.next_page()
                self.grid.row_offset = 0
                self.grid.curr_row = self.pager.page_start
            else:
                self.grid.curr_row = self.pager.total_rows - 1
        else:
            self.grid.move_down()
        self._ensure_row_in_page()

    def move_up(self):
        if self.grid.curr_row - 1 < self.pager.page_start:
            if self.pager.page_index > 0:
                self.pager.prev_page()
                self.grid.row_offset = 0
                self.grid.curr_row = max(self.pager.page_start, self.pager.page_end - 1)
            else:
                self.grid.curr_row = 0
        else:
            self.grid.move_up()
        self._ensure_row_in_page()

    def jump_rows_percent(self, pct, direction):
        target = self.pager.jump_rows_percent(pct, direction)
        self.grid.curr_row = target
        # adjust page if needed
        while self.grid.curr_row >= self.pager.page_end and self.pager.page_end < self.pager.total_rows:
            self.pager.next_page()
        while self.grid.curr_row < self.pager.page_start and self.pager.page_index > 0:
            self.pager.prev_page()
        self.grid.row_offset = 0
        self._ensure_row_in_page()

    def jump_page_edge(self, direction):
        target = self.pager.jump_page_edge(direction)
        self.grid.curr_row = target
        self.grid.row_offset = 0
        self._ensure_row_in_page()

    def jump_first_col(self):
        self.grid.curr_col = 0
        self.grid.col_offset = 0

    def jump_last_col(self):
        self.grid.curr_col = max(0, len(self.grid.df.columns) - 1)
        self.grid.col_offset = max(0, self.grid.curr_col - 1)

    def jump_cols_percent(self, pct, direction):
        total_cols = len(self.grid.df.columns)
        if total_cols == 0:
            return
        jump = max(1, int(total_cols * pct))
        if direction == 'right':
            self.grid.curr_col = min(total_cols - 1, self.grid.curr_col + jump)
        else:
            self.grid.curr_col = max(0, self.grid.curr_col - jump)
        # clamp col_offset if needed
        if self.grid.curr_col < self.grid.col_offset:
            self.grid.col_offset = self.grid.curr_col
        # no max_cols info here; grid.draw will adjust col_offset based on window
