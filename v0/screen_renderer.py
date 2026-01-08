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

        # Clear footer/output region deterministically to avoid artifacts
        for y in range(usable_height, max_y):
            stdscr.move(y, 0)
            stdscr.clrtoeol()

        df = state.df
        rows, cols = df.shape

        # Determine which rows to display
        display_rows = []
        truncated = False

        ELLIPSIS = -1
        ELLIPSIS = -1
        if state.show_all_rows or rows <= HEAD_ROWS + TAIL_ROWS + 10:
            display_rows = list(range(rows))
        else:
            display_rows = list(range(HEAD_ROWS))
            display_rows.append(ELLIPSIS)  # marker for ellipsis
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

            if r == -1:
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
            dtype = str(df.dtypes.iloc[state.curr_col])
        except Exception:
            pass

        if state.mode == 'command':
            max_cmd_height = max(1, min(7, max_y // 3))
            cmd_width = max_x - 1
            # Clear command pane area to avoid artifacts
            pane_top = max_y - 1 - max_cmd_height
            for cy in range(pane_top, max_y - 1):
                if cy >= 0:
                    stdscr.move(cy, 0)
                    stdscr.clrtoeol()
            text = state.command_buffer
            wrapped = [text[i:i+cmd_width] for i in range(0, len(text), cmd_width)] or ['']
            cursor = state.command_cursor
            cursor_row = cursor // cmd_width
            if cursor_row < state.command_scroll:
                state.command_scroll = cursor_row
            elif cursor_row >= state.command_scroll + max_cmd_height:
                state.command_scroll = cursor_row - max_cmd_height + 1
            visible = wrapped[state.command_scroll:state.command_scroll + max_cmd_height]
            start_y = max_y - 1 - len(visible)
            for i, line in enumerate(visible):
                y = start_y + i
                stdscr.addstr(y, 0, ':')
                for j, ch in enumerate(line.ljust(cmd_width)):
                    global_idx = (state.command_scroll + i) * cmd_width + j
                    attr = curses.A_REVERSE if global_idx == state.command_cursor else 0
                    stdscr.addstr(y, 1 + j, ch, attr)
                # cursor at end of line
                end_idx = (state.command_scroll + i) * cmd_width + len(line)
                if state.command_cursor == end_idx:
                    stdscr.addstr(y, 1 + len(line), ' ', curses.A_REVERSE)
            left = ''
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
        # Do not render output pane while in command mode; clear its area to avoid artifacts
        if state.mode == 'command':
            # Clear possible output pane region
            for oy in range(0, max_y - 1):
                # Only clear rows that could overlap command pane area
                if oy >= max_y - 1 - max(1, min(7, max_y // 3)):
                    continue
                # Leave grid rows intact; clear only lines below grid area
                # Conservative clear near bottom
                if oy >= max_y - 10:
                    stdscr.move(oy, 0)
                    stdscr.clrtoeol()
        elif state.command_output:
            lines = state.command_output.splitlines()
            max_lines = max_y - 3
            start_y = max_y - 2 - min(len(lines), max_lines)
            for i, line in enumerate(lines[-max_lines:]):
                stdscr.addstr(start_y + i, 0, line[:max_x].ljust(max_x))
            # Render once: clear output immediately to avoid ghosting
            state.command_output = None

        stdscr.refresh()
