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
            curses.init_pair(
                self.PAIR_CURSOR_INSERT, curses.COLOR_BLACK, curses.COLOR_WHITE
            )
            curses.init_pair(
                self.PAIR_CURSOR_NORMAL_BG, curses.COLOR_BLACK, curses.COLOR_BLACK
            )
            curses.init_pair(
                self.PAIR_CURSOR_NORMAL_CHAR, curses.COLOR_WHITE, curses.COLOR_BLACK
            )
            curses.init_pair(
                self.PAIR_CELL_ACTIVE_TEXT, curses.COLOR_BLACK, curses.COLOR_WHITE
            )
        except curses.error:
            pass

        self.curr_row = 0
        self.curr_col = 0
        self.row_offset = 0
        self.col_offset = 0
        self.highlight_mode = "cell"

        self.rendered_col_widths = {}

    def get_col_width(self, col_idx):
        if col_idx < 0 or col_idx >= len(self.df.columns):
            return self.MAX_COL_WIDTH
        col = self.df.columns[col_idx]
        max_len = len(str(col))
        for v in self.df[col]:
            if v is None or pd.isna(v):
                s = ""
            else:
                s = str(v)
            max_len = max(max_len, len(s))
        return min(self.MAX_COL_WIDTH, max_len + 2)

    def get_rendered_col_width(self, col_idx):
        return self.rendered_col_widths.get(col_idx, self.get_col_width(col_idx))

    def adjust_col_viewport(self, win=None):
        """Force column viewport adjustment so curr_col is visible.
        Call this after big cursor jumps (especially to last/first column)."""
        if len(self.df.columns) == 0:
            self.col_offset = 0
            return

        # Use real window dimensions if available
        if win is not None:
            h, w = win.getmaxyx()
        else:
            h, w = 24, 120  # reasonable fallback

        row_w = max(3, len(str(len(self.df))) + 1)
        avail_w = max(20, w - (row_w + 1))  # prevent tiny/negative avail width

        # Calculate approximate visible columns using header widths only (cheap, avoids full DF scans)
        header_widths = [
            min(self.MAX_COL_WIDTH, len(str(col)) + 2) for col in self.df.columns
        ]

        visible_count = 0
        used = 0
        for cw in header_widths[self.col_offset :]:
            if used + cw + 1 > avail_w:
                break
            used += cw + 1
            visible_count += 1

        visible_count = max(1, visible_count)

        # Core adjustment
        if self.curr_col < self.col_offset:
            self.col_offset = self.curr_col
        elif self.curr_col >= self.col_offset + visible_count:
            self.col_offset = self.curr_col - visible_count + 1

        # ────────────────────────────────────────────────────────────────
        # CRITICAL SAFETY: Never allow negative offset or overflow
        # This prevents crashes on repeated left jumps (Ctrl+H)
        # ────────────────────────────────────────────────────────────────
        self.col_offset = max(0, self.col_offset)

        max_possible_offset = max(0, len(self.df.columns) - visible_count)
        self.col_offset = min(self.col_offset, max_possible_offset)

    # ---------- navigation ----------
    def move_left(self):
        self.curr_col = max(0, self.curr_col - 1)
        self.highlight_mode = "cell"

    def move_right(self):
        self.curr_col = min(len(self.df.columns) - 1, self.curr_col + 1)
        self.highlight_mode = "cell"

    def move_down(self):
        self.curr_row = min(len(self.df) - 1, self.curr_row + 1)
        self.highlight_mode = "cell"

    def move_up(self):
        self.curr_row = max(0, self.curr_row - 1)
        self.highlight_mode = "cell"

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
        row_lines=1,
    ):
        win.erase()
        h, w = win.getmaxyx()
        row_block_height = max(1, row_lines)

        if page_end is None:
            page_end = len(self.df)
        total_rows = max(0, page_end - page_start)

        # compute column widths using only the page slice
        widths = []
        df_slice = self.df.iloc[page_start:page_end]
        for col in df_slice.columns:
            max_len = len(str(col))
            for v in df_slice[col]:
                s = "" if (v is None or pd.isna(v)) else str(v)
                max_len = max(max_len, len(s))
            widths.append(min(self.MAX_COL_WIDTH, max_len + 2))

        row_w = max(3, len(str(max(page_end - 1, 0))) + 1)

        max_rows = max(1, (h - 3) // row_block_height)
        avail_w = w - (row_w + 1)

        max_cols = 0
        used = 0
        for cw in widths[self.col_offset :]:
            if used + cw + 1 > avail_w:
                break
            used += cw + 1
            max_cols += 1
        max_cols = max(1, max_cols)

        # -----------------------------------------------------------------------
        # Safety net - prevent negative or invalid offset on every draw
        # This protects against all kinds of jumps (Ctrl+H/L, ,h, ,l)
        # -----------------------------------------------------------------------
        self.col_offset = max(0, self.col_offset)
        self.col_offset = min(self.col_offset, len(self.df.columns) - max_cols)

        # Row adjustment
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

        # Column adjustment (runs every draw)
        if self.curr_col < self.col_offset:
            self.col_offset = self.curr_col
        elif self.curr_col >= self.col_offset + max_cols:
            self.col_offset = self.curr_col - max_cols + 1

        # Final safety after all adjustments
        self.col_offset = max(0, self.col_offset)

        visible_rows = range(
            page_start + self.row_offset,
            min(page_end, page_start + self.row_offset + max_rows),
        )
        visible_cols = range(
            self.col_offset, min(len(df_slice.columns), self.col_offset + max_cols)
        )

        self.rendered_col_widths = {c: widths[c] for c in visible_cols}

        def _wrap_cell(text: str, width: int, max_lines: int):
            if width <= 0:
                return [""] * max_lines
            lines: list[str] = []
            parts = text.split("\n") if text else [""]
            for part in parts:
                if part == "":
                    lines.append("")
                else:
                    for i in range(0, len(part), width):
                        lines.append(part[i : i + width])
                if len(lines) >= max_lines:
                    break
            if not lines:
                lines.append("")
            lines = lines[:max_lines]
            while len(lines) < max_lines:
                lines.append("")
            return lines

        # header
        x = row_w + 1
        for c in visible_cols:
            cw = widths[c]
            eff_cw = min(cw, max(1, w - x - 1))
            self.rendered_col_widths[c] = eff_cw
            name = str(df_slice.columns[c])[:eff_cw].rjust(eff_cw)
            win.addnstr(1, x, name, eff_cw, curses.A_BOLD)
            x += eff_cw + 1

        # rows
        base_y = 2
        for idx, r in enumerate(visible_rows):
            row_y = base_y + idx * row_block_height
            if row_y >= h - 1:
                break
            win.addnstr(row_y, 0, str(r).rjust(row_w), row_w)
            x = row_w + 1
            for c in visible_cols:
                cw = widths[c]
                eff_cw = min(self.rendered_col_widths.get(c, cw), max(1, w - x - 1))

                is_edit_target = editing and r == edit_row and c == edit_col
                if is_edit_target:
                    text = edit_buffer or ""
                else:
                    val = self.df.iloc[r, c]
                    text = "" if (val is None or pd.isna(val)) else str(val)

                start = edit_hscroll if is_edit_target else 0
                wrapped_lines = _wrap_cell(text[start:], eff_cw, row_block_height)

                attr = 0
                if not editing:
                    active_cell = (
                        (self.highlight_mode == "row" and r == self.curr_row)
                        or (self.highlight_mode == "column" and c == self.curr_col)
                        or (
                            self.highlight_mode == "cell"
                            and r == self.curr_row
                            and c == self.curr_col
                        )
                    )
                    if active_cell:
                        attr = curses.color_pair(self.PAIR_CELL_ACTIVE_TEXT)

                cursor_line = None
                cursor_col = None
                if is_edit_target and edit_cursor is not None:
                    relative_pos = max(0, edit_cursor - start)
                    cursor_line = min(row_block_height - 1, relative_pos // eff_cw)
                    cursor_col = relative_pos % eff_cw

                for line_idx, line_text in enumerate(wrapped_lines):
                    line_y = row_y + line_idx
                    if line_y >= h - 1:
                        break
                    visible_len = len(line_text)
                    cell = line_text.rjust(eff_cw)
                    win.addnstr(line_y, x, cell, eff_cw, attr)

                    if (
                        is_edit_target
                        and cursor_line is not None
                        and cursor_col is not None
                        and line_idx == cursor_line
                    ):
                        text_start_x = x + (eff_cw - visible_len)
                        pos = min(cursor_col, visible_len)
                        cx = text_start_x + pos
                        cx = max(x, min(x + eff_cw - 1, cx))
                        if insert_mode:
                            win.addnstr(line_y, cx, " ", 1, curses.A_REVERSE)
                        else:
                            if pos < visible_len and visible_len > 0:
                                ch = line_text[pos]
                                win.addch(line_y, cx, ch, curses.A_REVERSE)
                            else:
                                win.addnstr(line_y, cx, " ", 1, curses.A_REVERSE)
                x += eff_cw + 1

        win.refresh()

