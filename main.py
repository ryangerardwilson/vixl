#!/usr/bin/env python3
import curses
import sys
import os
import pandas as pd
import time  # for napms alternative
import termios

os.environ['TERM'] = 'xterm-256color'
os.environ.setdefault('ESCDELAY', '25')

def main(stdscr):
    # Disable terminal flow control (Ctrl+S, Ctrl+Q)
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    new = list(old)
    new[0] &= ~termios.IXON
    termios.tcsetattr(fd, termios.TCSADRAIN, new)

    try:
        if len(sys.argv) < 2:
            stdscr.addstr(0, 0, "Usage: vipd <file.csv or file.parquet>")
            stdscr.refresh()
            stdscr.getch()
            return

        file_path = sys.argv[1]
        if os.path.exists(file_path):
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            elif file_path.endswith('.parquet'):
                df = pd.read_parquet(file_path)
            else:
                stdscr.addstr(0, 0, "Unsupported file type.")
                stdscr.refresh()
                stdscr.getch()
                return
        else:
            df = pd.DataFrame()
            if file_path.endswith('.csv'):
                df.to_csv(file_path, index=False)
            elif file_path.endswith('.parquet'):
                df.to_parquet(file_path)
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
            max_w = max(len(col_names[c]), max(len(df.iloc[r, c]) for r in range(rows)) if rows > 0 else 0) + 2
            widths.append(max_w)

        # Initial positions
        curr_row = 0
        curr_col = 0
        voffset = 0
        hoffset = 0
        mode = 'normal'
        header_mode = False
        cell_cursor = 0
        cell_hoffset = 0
        edited_value = ''
        cut_buffer = None
        leader_active = False

        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)  # Black on Cyan for selected

        stdscr.nodelay(False)  # Blocking for simplicity

        def save_file():
            if file_path.endswith('.csv'):
                df.to_csv(file_path, index=bool(df.index.name))
            elif file_path.endswith('.parquet'):
                df.to_parquet(file_path)

        def show_message(msg):
            max_y, max_x = stdscr.getmaxyx()
            try:
                stdscr.addstr(max_y - 1, 0, msg[:max_x])
                stdscr.clrtoeol()
            except:
                pass
            stdscr.refresh()
            time.sleep(1)  # Show for 1 second
            # No need to clear, next draw will clear

        while True:
            max_y, max_x = stdscr.getmaxyx()
            available_height = max_y - 2 if max_y > 2 else max_y - 1  # Header at 0, data from 1, status at max_y-1
            available_width = max_x - index_width

            # Adjust voffset
            if not header_mode:
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
            attr = curses.color_pair(1) if header_mode else 0
            stdscr.addstr(0, x, index_name.ljust(index_width), attr)
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
                attr = curses.color_pair(1) if not header_mode and r == curr_row else 0
                stdscr.addstr(y, x, idx_str, attr)
                x += index_width
                for c in range(hoffset, cols):
                    if x + widths[c] > max_x:
                        break
                    value = df.iloc[r, c][:widths[c]-2].ljust(widths[c]-2)
                    attr = curses.color_pair(1) if mode == 'normal' and not header_mode and r == curr_row and c == curr_col else 0
                    stdscr.addstr(y, x, value, attr)
                    x += widths[c]
                y += 1

            # If in cell mode, overlay the editing
            if mode in ('cell_normal', 'insert'):
                if header_mode:
                    cell_y = 0
                else:
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
                        stdscr.move(curs_y, curs_x)

            # Turn cursor on/off
            if mode in ('cell_normal', 'insert'):
                curses.curs_set(1)
            else:
                stdscr.move(max_y - 1, 0)
                curses.curs_set(0)

            stdscr.refresh()

            try:
                key = stdscr.getch()
            except KeyboardInterrupt:
                if mode in ('cell_normal', 'insert'):
                    if header_mode:
                        col_names[curr_col] = edited_value
                        max_w = max(len(edited_value), max(len(df.iloc[r, curr_col]) for r in range(rows)) if rows > 0 else len(edited_value)) + 2
                        widths[curr_col] = max_w
                    else:
                        df.iloc[curr_row, curr_col] = edited_value
                        max_w = max(len(col_names[curr_col]), max(len(df.iloc[r, curr_col]) for r in range(rows)) if rows > 0 else 0) + 2
                        widths[curr_col] = max_w
                save_file()
                break

            if mode == 'normal':
                if leader_active:
                    leader_active = False
                    if key == ord('n'):
                        next_key = stdscr.getch()
                        if next_key == ord('c'):
                            # new column
                            new_col_name = f"new_col_{cols}"
                            df[new_col_name] = [''] * rows
                            df = df.astype(str)
                            col_names.append(new_col_name)
                            cols += 1
                            widths.append(len(new_col_name) + 2)
                        elif next_key == ord('r'):
                            # new row
                            insert_idx = curr_row + 1
                            new_row = pd.Series([''] * cols, index=col_names)
                            df = pd.concat([df.iloc[:insert_idx], new_row.to_frame().T, df.iloc[insert_idx:]]).reset_index(drop=True)
                            df = df.astype(str)
                            rows += 1
                            index_values = [str(i) for i in df.index]
                            index_width = max(len(index_name), max(len(idx) for idx in index_values)) + 2 if rows > 0 else 4
                elif key == ord(','):
                    leader_active = True
                elif key == ord('q'):
                    # Save before quit
                    save_file()
                    break
                elif key == 19:  # Ctrl+S
                    save_file()
                    show_message("Saved!")
                elif key == 3:  # Ctrl+C
                    save_file()
                    break
                elif key == 23:  # Ctrl+W
                    header_mode = not header_mode
                    if header_mode:
                        curr_row = 0  # Reset row to 0 when entering header mode
                elif key == ord('d'):
                    next_key = stdscr.getch()
                    if next_key == ord('d'):
                        if header_mode:
                            # cut column
                            if cols > 0:
                                cut_buffer = {'type': 'col', 'data': df.iloc[:, curr_col], 'name': col_names[curr_col]}
                                df = df.drop(columns=col_names[curr_col])
                                df = df.astype(str)
                                col_names = df.columns.tolist()
                                cols -= 1
                                widths.pop(curr_col)
                                if curr_col >= cols:
                                    curr_col = cols - 1 if cols > 0 else 0
                        else:
                            # cut row
                            if rows > 0:
                                cut_buffer = {'type': 'row', 'data': df.iloc[curr_row]}
                                df = df.drop(df.index[curr_row])
                                df = df.reset_index(drop=True)
                                df = df.astype(str)
                                rows -= 1
                                index_values = [str(i) for i in df.index]
                                index_width = max(len(index_name), max(len(idx) for idx in index_values)) + 2 if rows > 0 else 4
                                if curr_row >= rows:
                                    curr_row = rows - 1 if rows > 0 else 0
                elif key == ord('p'):
                    if cut_buffer:
                        if header_mode and cut_buffer['type'] == 'col':
                            # paste column after current
                            insert_idx = curr_col + 1
                            df.insert(insert_idx, cut_buffer['name'], cut_buffer['data'])
                            df = df.astype(str)
                            col_names = df.columns.tolist()
                            cols += 1
                            new_w = max(len(cut_buffer['name']), max(len(v) for v in cut_buffer['data'])) + 2
                            widths.insert(insert_idx, new_w)
                        elif not header_mode and cut_buffer['type'] == 'row':
                            # paste row after current
                            insert_idx = curr_row + 1
                            new_row = pd.DataFrame([cut_buffer['data'].values], columns=col_names)
                            df = pd.concat([df.iloc[:insert_idx], new_row, df.iloc[insert_idx:]]).reset_index(drop=True)
                            df = df.astype(str)
                            rows += 1
                            index_values = [str(i) for i in df.index]
                            index_width = max(len(index_name), max(len(idx) for idx in index_values)) + 2 if rows > 0 else 4
                elif key == ord('i'):
                    if header_mode:
                        if cols > 0:
                            edited_value = col_names[curr_col]
                            cell_cursor = len(edited_value)
                            display_width = widths[curr_col] - 2
                            cell_hoffset = max(0, cell_cursor - display_width + 1)
                            mode = 'insert'
                    else:
                        if rows > 0 and cols > 0:
                            edited_value = df.iloc[curr_row, curr_col]
                            cell_cursor = len(edited_value)
                            display_width = widths[curr_col] - 2
                            cell_hoffset = max(0, cell_cursor - display_width + 1)
                            mode = 'insert'
                elif key in (curses.KEY_ENTER, 10, 13):
                    if header_mode:
                        if cols > 0:
                            mode = 'cell_normal'
                            edited_value = col_names[curr_col]
                            cell_cursor = 0
                            cell_hoffset = 0
                    else:
                        if rows > 0 and cols > 0:
                            mode = 'cell_normal'
                            edited_value = df.iloc[curr_row, curr_col]
                            cell_cursor = 0
                            cell_hoffset = 0
                elif not header_mode or key in (ord('h'), ord('l')):
                    if key == ord('h'):
                        if curr_col > 0:
                            curr_col -= 1
                    elif key == ord('l'):
                        if curr_col < cols - 1:
                            curr_col += 1
                    elif not header_mode and key == ord('j'):
                        if curr_row < rows - 1:
                            curr_row += 1
                    elif not header_mode and key == ord('k'):
                        if curr_row > 0:
                            curr_row -= 1
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
                elif key == 19:  # Ctrl+S
                    if header_mode:
                        col_names[curr_col] = edited_value
                        max_w = max(len(edited_value), max(len(df.iloc[r, curr_col]) for r in range(rows)) if rows > 0 else len(edited_value)) + 2
                        widths[curr_col] = max_w
                    else:
                        df.iloc[curr_row, curr_col] = edited_value
                        max_w = max(len(col_names[curr_col]), max(len(df.iloc[r, curr_col]) for r in range(rows)) if rows > 0 else 0) + 2
                        widths[curr_col] = max_w
                    save_file()
                    show_message("Saved!")
                elif key == 3:  # Ctrl+C
                    if header_mode:
                        col_names[curr_col] = edited_value
                        max_w = max(len(edited_value), max(len(df.iloc[r, curr_col]) for r in range(rows)) if rows > 0 else len(edited_value)) + 2
                        widths[curr_col] = max_w
                    else:
                        df.iloc[curr_row, curr_col] = edited_value
                        max_w = max(len(col_names[curr_col]), max(len(df.iloc[r, curr_col]) for r in range(rows)) if rows > 0 else 0) + 2
                        widths[curr_col] = max_w
                    save_file()
                    break
                elif key == 27:  # ESC
                    if header_mode:
                        col_names[curr_col] = edited_value
                        max_w = max(len(edited_value), max(len(df.iloc[r, curr_col]) for r in range(rows)) if rows > 0 else len(edited_value)) + 2
                        widths[curr_col] = max_w
                    else:
                        df.iloc[curr_row, curr_col] = edited_value
                        max_w = max(len(col_names[curr_col]), max(len(df.iloc[r, curr_col]) for r in range(rows)) if rows > 0 else 0) + 2
                        widths[curr_col] = max_w
                    mode = 'normal'
            elif mode == 'insert':
                if key == 27:  # ESC
                    mode = 'cell_normal'
                elif key == 19:  # Ctrl+S
                    if header_mode:
                        col_names[curr_col] = edited_value
                        max_w = max(len(edited_value), max(len(df.iloc[r, curr_col]) for r in range(rows)) if rows > 0 else len(edited_value)) + 2
                        widths[curr_col] = max_w
                    else:
                        df.iloc[curr_row, curr_col] = edited_value
                        max_w = max(len(col_names[curr_col]), max(len(df.iloc[r, curr_col]) for r in range(rows)) if rows > 0 else 0) + 2
                        widths[curr_col] = max_w
                    save_file()
                    show_message("Saved!")
                elif key == 3:  # Ctrl+C
                    if header_mode:
                        col_names[curr_col] = edited_value
                        max_w = max(len(edited_value), max(len(df.iloc[r, curr_col]) for r in range(rows)) if rows > 0 else len(edited_value)) + 2
                        widths[curr_col] = max_w
                    else:
                        df.iloc[curr_row, curr_col] = edited_value
                        max_w = max(len(col_names[curr_col]), max(len(df.iloc[r, curr_col]) for r in range(rows)) if rows > 0 else 0) + 2
                        widths[curr_col] = max_w
                    save_file()
                    break
                elif key in (curses.KEY_ENTER, 10, 13):
                    if not header_mode:
                        df.iloc[curr_row, curr_col] = edited_value
                        max_w = max(len(col_names[curr_col]), max(len(df.iloc[r, curr_col]) for r in range(rows)) if rows > 0 else 0) + 2
                        widths[curr_col] = max_w
                        if curr_row < rows - 1:
                            curr_row += 1
                            edited_value = df.iloc[curr_row, curr_col]
                            cell_cursor = len(edited_value)
                            display_width = widths[curr_col] - 2
                            cell_hoffset = max(0, cell_cursor - display_width + 1)
                elif key == 9:  # Tab
                    if not header_mode:
                        df.iloc[curr_row, curr_col] = edited_value
                        max_w = max(len(col_names[curr_col]), max(len(df.iloc[r, curr_col]) for r in range(rows)) if rows > 0 else 0) + 2
                        widths[curr_col] = max_w
                        if curr_col < cols - 1:
                            curr_col += 1
                            edited_value = df.iloc[curr_row, curr_col]
                            cell_cursor = len(edited_value)
                            display_width = widths[curr_col] - 2
                            cell_hoffset = max(0, cell_cursor - display_width + 1)
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

    finally:
        # Restore terminal settings
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

if __name__ == "__main__":
    curses.wrapper(main)
