#!/usr/bin/env python3
import curses
import sys
import os
import pandas as pd

os.environ['TERM'] = 'xterm-256color'
os.environ.setdefault('ESCDELAY', '25')

def main(stdscr):
    if len(sys.argv) < 2:
        stdscr.addstr(0, 0, "Usage: vipd <file.csv or file.parquet>")
        stdscr.refresh()
        stdscr.getch()
        return

    file_path = sys.argv[1]
    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path)
    elif file_path.endswith('.parquet'):
        df = pd.read_parquet(file_path)
    else:
        stdscr.addstr(0, 0, "Unsupported file type.")
        stdscr.refresh()
        stdscr.getch()
        return

    df = df.astype(str)
    rows, cols = df.shape
    col_names = df.columns.tolist()
    index_name = df.index.name if df.index.name else ''
    index_values = [str(i) for i in df.index]

    # Calculate widths
    index_width = max(len(index_name), max(len(idx) for idx in index_values)) + 2 if rows > 0 else 4
    widths = []
    for c in range(cols):
        max_w = max(len(col_names[c]), max(len(df.iloc[r, c]) for r in range(rows))) + 2
        widths.append(max_w)

    # Initial positions
    curr_row = 0
    curr_col = 0
    voffset = 0
    hoffset = 0
    mode = 'normal'
    cell_cursor = 0
    cell_hoffset = 0
    edited_value = ''

    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)  # Black on Cyan for selected

    stdscr.nodelay(False)  # Blocking for simplicity

    while True:
        max_y, max_x = stdscr.getmaxyx()
        available_height = max_y - 1  # Header at 0, data from 1
        available_width = max_x - index_width

        # Adjust voffset
        if curr_row < voffset:
            voffset = curr_row
        elif curr_row >= voffset + available_height:
            voffset = curr_row - available_height + 1
        voffset = max(0, min(voffset, rows - available_height))

        # Adjust hoffset to make current column visible
        left_x = index_width
        for c in range(hoffset, curr_col):
            left_x += widths[c]
        right_x = left_x + widths[curr_col]
        if curr_col < hoffset:
            hoffset = curr_col
        while right_x > max_x and hoffset < curr_col:
            left_x -= widths[hoffset]
            hoffset += 1
            right_x = left_x + widths[curr_col]
        hoffset = max(0, hoffset)

        stdscr.clear()

        # Draw header
        x = 0
        stdscr.addstr(0, x, index_name.ljust(index_width))
        x += index_width
        for c in range(hoffset, cols):
            if x + widths[c] > max_x:
                break
            name = col_names[c][:widths[c]-2].ljust(widths[c]-2)
            attr = curses.color_pair(1) if c == curr_col else 0
            stdscr.addstr(0, x, name, attr)
            x += widths[c]

        # Draw rows
        y = 1
        for r in range(voffset, min(voffset + available_height, rows)):
            x = 0
            idx_str = index_values[r].ljust(index_width - 2)
            attr = curses.color_pair(1) if r == curr_row else 0
            stdscr.addstr(y, x, idx_str, attr)
            x += index_width
            for c in range(hoffset, cols):
                if x + widths[c] > max_x:
                    break
                value = df.iloc[r, c][:widths[c]-2].ljust(widths[c]-2)
                attr = curses.color_pair(1) if mode == 'normal' and r == curr_row and c == curr_col else 0
                stdscr.addstr(y, x, value, attr)
                x += widths[c]
            y += 1

        # If in cell mode, overlay the editing
        if mode in ('cell_normal', 'insert'):
            cell_y = 1 + (curr_row - voffset)
            cell_x = index_width
            for c in range(hoffset, curr_col):
                cell_x += widths[c]
            display_width = widths[curr_col] - 2
            if cell_x + display_width <= max_x:
                display_str = edited_value[cell_hoffset:cell_hoffset + display_width].ljust(display_width)
                stdscr.addstr(cell_y, cell_x, display_str, curses.color_pair(1))
                curs_x = cell_x + (cell_cursor - cell_hoffset)
                curs_y = cell_y
                if curs_x < max_x:
                    curses.curs_set(1)
                    stdscr.move(curs_y, curs_x)
        else:
            curses.curs_set(0)

        stdscr.refresh()

        key = stdscr.getch()

        if mode == 'normal':
            if key == ord('q'):
                # Save before quit
                if file_path.endswith('.csv'):
                    df.to_csv(file_path, index=bool(df.index.name))
                elif file_path.endswith('.parquet'):
                    df.to_parquet(file_path)
                break
            elif key == ord('h'):
                if curr_col > 0:
                    curr_col -= 1
            elif key == ord('l'):
                if curr_col < cols - 1:
                    curr_col += 1
            elif key == ord('j'):
                if curr_row < rows - 1:
                    curr_row += 1
            elif key == ord('k'):
                if curr_row > 0:
                    curr_row -= 1
            elif key in (curses.KEY_ENTER, 10, 13):
                if rows > 0 and cols > 0:
                    mode = 'cell_normal'
                    edited_value = df.iloc[curr_row, curr_col]
                    cell_cursor = 0
                    cell_hoffset = 0
        elif mode == 'cell_normal':
            if key == ord('h'):
                if cell_cursor > 0:
                    cell_cursor -= 1
                    if cell_cursor < cell_hoffset:
                        cell_hoffset = cell_cursor
            elif key == ord('l'):
                if cell_cursor < len(edited_value):
                    cell_cursor += 1
                    display_width = widths[curr_col] - 2
                    if cell_cursor >= cell_hoffset + display_width:
                        cell_hoffset = cell_cursor - display_width + 1
            elif key == ord('i'):
                mode = 'insert'
            elif key == 27:  # ESC
                df.iloc[curr_row, curr_col] = edited_value
                # Recalculate width for this column
                max_w = max(len(col_names[curr_col]), max(len(df.iloc[r, curr_col]) for r in range(rows))) + 2
                widths[curr_col] = max_w
                mode = 'normal'
        elif mode == 'insert':
            if key == 27:  # ESC
                mode = 'cell_normal'
            elif key == curses.KEY_BACKSPACE:
                if cell_cursor > 0:
                    edited_value = edited_value[:cell_cursor-1] + edited_value[cell_cursor:]
                    cell_cursor -= 1
                    if cell_cursor < cell_hoffset:
                        cell_hoffset = cell_cursor
            elif key == curses.KEY_LEFT:
                if cell_cursor > 0:
                    cell_cursor -= 1
                    if cell_cursor < cell_hoffset:
                        cell_hoffset = cell_cursor
            elif key == curses.KEY_RIGHT:
                if cell_cursor < len(edited_value):
                    cell_cursor += 1
                    display_width = widths[curr_col] - 2
                    if cell_cursor >= cell_hoffset + display_width:
                        cell_hoffset = cell_cursor - display_width + 1
            elif 32 <= key <= 126:
                edited_value = edited_value[:cell_cursor] + chr(key) + edited_value[cell_cursor:]
                cell_cursor += 1
                display_width = widths[curr_col] - 2
                if cell_cursor >= cell_hoffset + display_width:
                    cell_hoffset = cell_cursor - display_width + 1

if __name__ == "__main__":
    curses.wrapper(main)
