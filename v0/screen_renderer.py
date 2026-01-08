import curses
import math


CELL_WIDTH = 12
HEAD_ROWS = 5
TAIL_ROWS = 5


class ScreenRenderer:
    """
    Simple grid renderer.
    - Fixed-width cells
    - Explicit row truncation
    - Honest navigation semantics
    """

    def __init__(self, stdscr):
        self.stdscr = stdscr

    def draw(self, state):
        stdscr = self.stdscr
        stdscr.clear()

        if state.df is None:
            stdscr.addstr(0, 0, "No data loaded")
            stdscr.refresh()
            return

        max_y, max_x = stdscr.getmaxyx()
        usable_height = max_y - 2  # leave space for status bar

        df = state.df
        rows, cols = df.shape

        # Determine which rows to display
        display_rows = []
        truncated = False

        if state.show_all_rows or rows <= HEAD_ROWS + TAIL_ROWS + 10:
            display_rows = list(range(rows))
        else:
            display_rows = list(range(HEAD_ROWS))
            display_rows.append(None)  # marker for ellipsis
            display_rows.extend(range(rows - TAIL_ROWS, rows))
            truncated = True

        # Compute visible columns based on width
        col_width = CELL_WIDTH + 1
        max_visible_cols = max(1, (max_x - 4) // col_width)
        start_col = state.col_offset
        end_col = min(cols, start_col + max_visible_cols)
        visible_cols = list(range(start_col, end_col))

        # Draw header
        y = 0
        x = 4
        for c in visible_cols:
            name = str(state.col_names[c])[:CELL_WIDTH].rjust(CELL_WIDTH)
            stdscr.addstr(y, x, name, curses.A_BOLD)
            x += col_width

        y += 1

        # Draw rows
        for r in display_rows:
            if y >= usable_height:
                break

            if r is None:
                stdscr.addstr(y, 0, "   ...")
                y += 1
                continue

            # Row index
            row_label = str(r).rjust(3)
            stdscr.addstr(y, 0, row_label)

            x = 4
            for c in visible_cols:
                val = df.iloc[r, c]
                if val is None or (isinstance(val, float) and math.isnan(val)):
                    text = ""
                else:
                    text = str(val)
                cell = text[:CELL_WIDTH].rjust(CELL_WIDTH)

                attr = 0
                if state.highlight_mode == 'row' and r == state.curr_row:
                    attr = curses.A_REVERSE
                elif state.highlight_mode == 'column' and c == state.curr_col:
                    attr = curses.A_REVERSE
                elif state.highlight_mode == 'cell' and r == state.curr_row and c == state.curr_col:
                    attr = curses.A_REVERSE

                stdscr.addstr(y, x, cell, attr)
                x += col_width

            y += 1

        # Status bar
        col_name = ''
        dtype = ''
        try:
            col_name = state.col_names[state.curr_col]
            dtype = str(df.dtypes[state.curr_col])
        except Exception:
            pass

        if state.mode == 'command':
            left = f":{state.command_buffer}"
        else:
            left = f" MODE: {state.mode.upper()} | df.{col_name}.dtype > {dtype} "

        shape = ''
        try:
            shape = f" ({df.shape[0]}, {df.shape[1]})"
        except Exception:
            pass
        right = f" {state.file_path or ''}{shape}"
        bar = left
        if len(left) + len(right) < max_x:
            bar = left + ' ' * (max_x - len(left) - len(right)) + right

        try:
            if max_y > 0 and max_x > 0:
                stdscr.addstr(max_y - 1, 0, bar[:max_x])
        except curses.error:
            pass

        # Output pane (above status bar)
        if state.command_output:
            lines = state.command_output.splitlines()
            max_lines = max_y - 3
            start_y = max_y - 2 - min(len(lines), max_lines)
            for i, line in enumerate(lines[-max_lines:]):
                stdscr.addstr(start_y + i, 0, line[:max_x].ljust(max_x))

        stdscr.refresh()
