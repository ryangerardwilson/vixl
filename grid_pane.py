# ~/Apps/vixl/grid_pane.py
import curses
import pandas as pd


class GridPane:
    PAIR_CELL_ACTIVE = 1
    PAIR_CURSOR_INSERT = 2
    PAIR_CURSOR_NORMAL_BG = 3
    PAIR_CURSOR_NORMAL_CHAR = 4
    PAIR_CELL_ACTIVE_TEXT = 5
    PAIR_CELL_TEXT = 6
    MAX_COL_WIDTH = 40

    def __init__(self, df):
        self.df = df
        try:
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(self.PAIR_CELL_ACTIVE, -1, curses.COLOR_WHITE)
            curses.init_pair(self.PAIR_CELL_TEXT, curses.COLOR_WHITE, -1)
            curses.init_pair(
                self.PAIR_CURSOR_INSERT, curses.COLOR_BLACK, curses.COLOR_WHITE
            )
            curses.init_pair(self.PAIR_CURSOR_NORMAL_BG, curses.COLOR_BLACK, -1)
            curses.init_pair(self.PAIR_CURSOR_NORMAL_CHAR, curses.COLOR_WHITE, -1)
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

        # Visual mode rendering state (owned by controller; grid only renders)
        self.visual_active = False
        self.visual_rect = None  # (r0, r1, c0, c1)

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

    @staticmethod
    def _wrap_cell_line_count(text: str, width: int) -> int:
        if width <= 0:
            return 1
        parts = text.split("\n") if text else [""]
        lines = 0
        for part in parts:
            if part == "":
                lines += 1
            else:
                words = part.split(" ")
                current = ""
                for word in words:
                    if current == "":
                        if len(word) <= width:
                            current = word
                        else:
                            lines += max(1, (len(word) + width - 1) // width)
                    else:
                        if len(current) + 1 + len(word) <= width:
                            current = f"{current} {word}"
                        else:
                            lines += 1
                            if len(word) <= width:
                                current = word
                            else:
                                lines += max(1, (len(word) + width - 1) // width)
                                current = ""
                if current or current == "":
                    lines += 1
        return max(1, lines)

    def _compute_row_heights(
        self,
        page_rows,
        cols_for_height,
        widths,
        rendered_widths,
        row_lines,
        expanded_rows,
        expand_all_rows,
    ):
        expanded_rows = expanded_rows or set()
        total_cols = len(widths)
        heights: list[int] = []
        for abs_r in page_rows:
            base_height = max(1, row_lines)
            is_expanded = expand_all_rows or (abs_r in expanded_rows)
            if not is_expanded:
                heights.append(base_height)
                continue

            max_lines = base_height
            for c in cols_for_height:
                if c < 0 or c >= total_cols:
                    continue
                eff_cw = max(1, rendered_widths.get(c, widths[c]))
                try:
                    val = self.df.iloc[abs_r, c]
                except Exception:
                    val = None
                text = "" if (val is None or pd.isna(val)) else str(val)
                max_lines = max(max_lines, self._wrap_cell_line_count(text, eff_cw))
            heights.append(max_lines)
        return heights

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
        page_start=0,
        page_end=None,
        row_lines=1,
        expanded_rows=None,
        expand_all_rows=False,
    ):
        win.erase()
        try:
            win.bkgd(" ", curses.color_pair(self.PAIR_CELL_TEXT))
        except curses.error:
            pass
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
                s = "" if (v is None or pd.isna(v)) else str(v)
                max_len = max(max_len, len(s))
            widths.append(min(self.MAX_COL_WIDTH, max_len + 2))

        row_w = max(3, len(str(max(page_end - 1, 0))) + 1)

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

        # Column adjustment (runs every draw)
        if self.curr_col < self.col_offset:
            self.col_offset = self.curr_col
        elif self.curr_col >= self.col_offset + max_cols:
            self.col_offset = self.curr_col - max_cols + 1

        # Final safety after all adjustments
        self.col_offset = max(0, self.col_offset)

        visible_cols = range(
            self.col_offset, min(len(df_slice.columns), self.col_offset + max_cols)
        )
        visible_cols = tuple(visible_cols)

        self.rendered_col_widths = {c: widths[c] for c in visible_cols}

        total_cols = len(df_slice.columns)
        cols_for_height = (
            tuple(range(total_cols)) if expand_all_rows else visible_cols
        )

        def _wrap_cell(text: str, width: int, max_lines: int):
            if width <= 0:
                return [""] * max_lines
            lines: list[str] = []
            parts = text.split("\n") if text else [""]
            for part in parts:
                if part == "":
                    lines.append("")
                else:
                    words = part.split(" ")
                    current = ""
                    for word in words:
                        if current == "":
                            if len(word) <= width:
                                current = word
                            else:
                                # hard-break overlong word
                                for i in range(0, len(word), width):
                                    lines.append(word[i : i + width])
                                    if len(lines) >= max_lines:
                                        break
                                if len(lines) >= max_lines:
                                    break
                                current = ""
                        else:
                            if len(current) + 1 + len(word) <= width:
                                current = f"{current} {word}"
                            else:
                                lines.append(current)
                                if len(lines) >= max_lines:
                                    break
                                if len(word) <= width:
                                    current = word
                                else:
                                    for i in range(0, len(word), width):
                                        lines.append(word[i : i + width])
                                        if len(lines) >= max_lines:
                                            break
                                    current = ""
                        if len(lines) >= max_lines:
                            break
                    if len(lines) >= max_lines:
                        break
                    if current or current == "":
                        lines.append(current)
                if len(lines) >= max_lines:
                    break
            if not lines:
                lines.append("")
            lines = lines[:max_lines]
            while len(lines) < max_lines:
                lines.append("")
            return lines

        def _wrap_line_count(text: str, width: int) -> int:
            if width <= 0:
                return 1
            parts = text.split("\n") if text else [""]
            lines = 0
            for part in parts:
                if part == "":
                    lines += 1
                else:
                    words = part.split(" ")
                    current = ""
                    for word in words:
                        if current == "":
                            if len(word) <= width:
                                current = word
                            else:
                                lines += max(1, (len(word) + width - 1) // width)
                        else:
                            if len(current) + 1 + len(word) <= width:
                                current = f"{current} {word}"
                            else:
                                lines += 1
                                if len(word) <= width:
                                    current = word
                                else:
                                    lines += max(1, (len(word) + width - 1) // width)
                                    current = ""
                    if current or current == "":
                        lines += 1
            return max(1, lines)


        # header
        x = row_w + 1
        for c in visible_cols:
            cw = widths[c]
            eff_cw = min(cw, max(1, w - x - 1))
            self.rendered_col_widths[c] = eff_cw
            name = str(df_slice.columns[c])[:eff_cw].rjust(eff_cw)
            win.addnstr(1, x, name, eff_cw, curses.A_BOLD)
            x += eff_cw + 1

        # Compute per-row heights (supports expansion)
        expanded_rows = expanded_rows or set()
        page_rows = list(range(page_start, page_end))
        row_heights: list[int] = []
        for abs_r in page_rows:
            base_height = max(1, row_lines)
            is_expanded = expand_all_rows or (abs_r in expanded_rows)
            if not is_expanded:
                row_heights.append(base_height)
                continue

            max_lines = base_height
            for c in cols_for_height:
                if c < 0 or c >= total_cols:
                    continue
                eff_cw = widths[c]
                val = self.df.iloc[abs_r, c]
                text = "" if (val is None or pd.isna(val)) else str(val)
                max_lines = max(max_lines, self._wrap_cell_line_count(text, eff_cw))
            row_heights.append(max_lines)

        base_y = 2
        max_height_budget = max(0, h - base_y - 1)

        if total_rows == 0:
            visible_rows = []
        else:
            curr_idx = min(max(self.curr_row - page_start, 0), len(page_rows) - 1)
            self.row_offset = min(max(self.row_offset, 0), len(page_rows) - 1)

            prefix = [0]
            for rh in row_heights:
                prefix.append(prefix[-1] + rh)

            offset = self.row_offset
            # ensure current row fits in view; slide offset forward if needed
            while (
                prefix[curr_idx + 1] - prefix[offset] > max_height_budget
                and offset < curr_idx
            ):
                offset += 1

            def _rows_from(start_idx: int):
                rows: list[int] = []
                used = 0
                for i in range(start_idx, len(page_rows)):
                    rh = row_heights[i]
                    if used + rh > max_height_budget and used > 0:
                        break
                    rows.append(page_rows[i])
                    used += rh
                    if used >= max_height_budget:
                        break
                if not rows and page_rows:
                    rows.append(page_rows[start_idx])
                return rows

            visible_rows = _rows_from(offset)
            if self.curr_row not in visible_rows:
                # try to back up to include current row
                offset = max(0, curr_idx)
                visible_rows = _rows_from(offset)
            self.row_offset = offset

        # rows
        visible_cols = tuple(visible_cols)
        y_cursor = base_y
        for r in visible_rows:
            idx_in_page = r - page_start
            row_h = (
                row_heights[idx_in_page]
                if idx_in_page < len(row_heights)
                else max(1, row_lines)
            )
            if y_cursor >= h - 1:
                break
            win.addnstr(y_cursor, 0, str(r).rjust(row_w), row_w)
            x = row_w + 1
            for c in visible_cols:
                cw = widths[c]
                eff_cw = min(self.rendered_col_widths.get(c, cw), max(1, w - x - 1))

                val = self.df.iloc[r, c]
                text = "" if (val is None or pd.isna(val)) else str(val)

                wrapped_lines = _wrap_cell(text, eff_cw, row_h)

                base_attr = curses.color_pair(self.PAIR_CELL_TEXT)
                attr = base_attr
                in_visual = False
                if self.visual_active and self.visual_rect:
                    r0, r1, c0, c1 = self.visual_rect
                    in_visual = r0 <= r <= r1 and c0 <= c <= c1

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
                    attr = base_attr | curses.A_REVERSE
                elif in_visual:
                    attr = base_attr | curses.A_STANDOUT

                eff_cw_int = int(eff_cw)
                for line_idx, line_text in enumerate(wrapped_lines):
                    line_y = y_cursor + line_idx
                    if line_y >= h - 1:
                        break
                    cell = line_text.rjust(eff_cw_int)
                    win.addnstr(line_y, x, cell, eff_cw_int, attr)

                x += eff_cw + 1

            y_cursor += row_h
            if y_cursor >= h - 1:
                break

        # footer line
        try:
            win.hline(h - 1, 0, " ", w)
        except curses.error:
            pass

        win.refresh()
