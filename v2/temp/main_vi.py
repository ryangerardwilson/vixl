import sys
import curses
import pandas as pd


def format_table(headers, rows, max_width):
    if not headers:
        return []
    cols = list(zip(*([headers] + rows))) if rows else [[h] for h in headers]
    widths = [min(max(len(str(cell)) for cell in col) + 2, max_width) for col in cols]

    def fmt_row(row):
        return "".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row))

    lines = [fmt_row(headers)]
    lines.append("".join("-" * w for w in widths))
    for row in rows:
        lines.append(fmt_row(row))
    return lines


def draw_table(win, headers, rows, max_rows):
    win.erase()
    max_width = win.getmaxyx()[1] - 2
    lines = format_table(headers, rows, max_width)
    for i, line in enumerate(lines[:max_rows]):
        win.addstr(i + 1, 1, line[:max_width])
    win.box()
    win.refresh()


def cursor_to_rowcol(buffer, cursor):
    lines = buffer.split("\n")
    idx = 0
    for r, line in enumerate(lines):
        if idx + len(line) >= cursor:
            return r, cursor - idx, lines
        idx += len(line) + 1
    return len(lines) - 1, len(lines[-1]), lines


def rowcol_to_cursor(lines, row, col):
    idx = 0
    for r in range(row):
        idx += len(lines[r]) + 1
    return idx + min(col, len(lines[row]))


# -------- motions --------

def move_word_forward(buf, cur):
    n = len(buf)
    i = cur
    while i < n and buf[i].isspace():
        i += 1
    while i < n and not buf[i].isspace():
        i += 1
    return i


def move_word_backward(buf, cur):
    i = max(0, cur - 1)
    while i > 0 and buf[i].isspace():
        i -= 1
    while i > 0 and not buf[i - 1].isspace():
        i -= 1
    return i


def handle_motion(ch, buffer, cursor):
    if ch == ord('h'):
        return max(0, cursor - 1)
    if ch == ord('l'):
        return min(len(buffer), cursor + 1)
    if ch == ord('w'):
        return move_word_forward(buffer, cursor)
    if ch == ord('b'):
        return move_word_backward(buffer, cursor)
    if ch == ord('0'):
        row, col, lines = cursor_to_rowcol(buffer, cursor)
        return rowcol_to_cursor(lines, row, 0)
    if ch == ord('$'):
        row, col, lines = cursor_to_rowcol(buffer, cursor)
        return rowcol_to_cursor(lines, row, len(lines[row]))
    if ch == ord('k'):
        row, col, lines = cursor_to_rowcol(buffer, cursor)
        if row > 0:
            return rowcol_to_cursor(lines, row - 1, col)
    if ch == ord('j'):
        row, col, lines = cursor_to_rowcol(buffer, cursor)
        if row < len(lines) - 1:
            return rowcol_to_cursor(lines, row + 1, col)
    return cursor


# --------------------------------

def draw_input(win, buffer, cursor, mode, visual_start):
    win.erase()
    win.box()
    h, w = win.getmaxyx()

    lines = buffer.split("\n")
    idx = 0
    cur_row = cur_col = 0

    for r, line in enumerate(lines):
        if idx + len(line) >= cursor:
            cur_row = r
            cur_col = cursor - idx
            break
        idx += len(line) + 1

    sel_a = sel_b = None
    if mode == "visual" and visual_start is not None:
        sel_a = min(visual_start, cursor)
        sel_b = max(visual_start, cursor)

    char_idx = 0
    for r, line in enumerate(lines[: h - 2]):
        for c, ch in enumerate(line[: w - 2]):
            attr = curses.A_REVERSE if sel_a is not None and sel_a <= char_idx < sel_b else 0
            win.addch(r + 1, c + 1, ch, attr)
            char_idx += 1
        char_idx += 1

    status = f" -- {mode.upper()} --"
    win.addstr(h - 1, w - len(status) - 2, status)

    cy = max(1, min(1 + cur_row, h - 2))
    cx = max(1, min(1 + cur_col, w - 2))
    win.move(cy, cx)
    win.refresh()


def curses_main(stdscr, df):
    curses.curs_set(1)
    stdscr.clear()
    stdscr.refresh()

    height, width = stdscr.getmaxyx()
    input_h = max(5, height * 2 // 5)
    table_h = height - input_h

    table_win = curses.newwin(table_h, width, 0, 0)
    input_win = curses.newwin(input_h, width, table_h, 0)

    headers = list(df.columns)
    rows = df.values.tolist()

    buffer = ""
    cursor = 0
    mode = "insert"
    pending = None
    leader = False
    yank = ""
    visual_start = None

    draw_table(table_win, headers, rows, table_h - 2)
    draw_input(input_win, buffer, cursor, mode, visual_start)

    while True:
        ch = stdscr.getch()

        if mode == "insert":
            if ch == 27:
                mode = "normal"
            elif ch in (curses.KEY_BACKSPACE, 127):
                if cursor > 0:
                    buffer = buffer[: cursor - 1] + buffer[cursor:]
                    cursor -= 1
            elif ch == 10:
                buffer = buffer[:cursor] + "\n" + buffer[cursor:]
                cursor += 1
            elif 32 <= ch <= 126:
                buffer = buffer[:cursor] + chr(ch) + buffer[cursor:]
                cursor += 1

        elif mode == "visual":
            if ch in (27, ord('v')):
                mode = "normal"
                visual_start = None
            elif ch == ord('d'):
                a = min(visual_start, cursor)
                b = max(visual_start, cursor)
                yank = buffer[a:b]
                buffer = buffer[:a] + buffer[b:]
                cursor = a
                mode = "normal"
                visual_start = None
            elif ch == ord('y'):
                a = min(visual_start, cursor)
                b = max(visual_start, cursor)
                yank = buffer[a:b]
                mode = "normal"
                visual_start = None
            else:
                cursor = handle_motion(ch, buffer, cursor)

        else:  # NORMAL MODE
            if leader:
                if ch == ord('e'):
                    row, col, lines = cursor_to_rowcol(buffer, cursor)
                    cursor = rowcol_to_cursor(lines, row, len(lines[row]))
                    mode = "insert"
                leader = False

            elif pending:
                if pending == 'd' and ch == ord('d'):
                    row, col, lines = cursor_to_rowcol(buffer, cursor)
                    yank = lines[row] + "\n"
                    del lines[row]
                    buffer = "\n".join(lines) if lines else ""
                    cursor = rowcol_to_cursor(lines, min(row, len(lines) - 1), 0) if lines else 0
                elif pending == 'y' and ch == ord('y'):
                    row, col, lines = cursor_to_rowcol(buffer, cursor)
                    yank = lines[row] + "\n"
                pending = None

            elif ch == ord(','):
                leader = True

            elif ch in (ord('d'), ord('y')):
                pending = chr(ch)

            elif ch == ord('v'):
                mode = "visual"
                visual_start = cursor

            elif ch == ord('o'):
                row, col, lines = cursor_to_rowcol(buffer, cursor)
                insert_at = rowcol_to_cursor(lines, row, len(lines[row]))
                buffer = buffer[:insert_at] + "\n" + buffer[insert_at:]
                cursor = insert_at + 1
                mode = "insert"

            elif ch == ord('O'):
                row, col, lines = cursor_to_rowcol(buffer, cursor)
                insert_at = rowcol_to_cursor(lines, row, 0)
                buffer = buffer[:insert_at] + "\n" + buffer[insert_at:]
                cursor = insert_at
                mode = "insert"

            elif ch == ord('p'):
                if yank:
                    buffer = buffer[:cursor] + yank + buffer[cursor:]
                    cursor += len(yank)

            elif ch == ord('i'):
                mode = "insert"

            else:
                cursor = handle_motion(ch, buffer, cursor)

        draw_input(input_win, buffer, cursor, mode, visual_start)


def main():
    if len(sys.argv) != 2:
        print("Usage: python main_vi.py <csv_file>")
        sys.exit(1)
    df = pd.read_csv(sys.argv[1])
    curses.wrapper(curses_main, df)


if __name__ == "__main__":
    main()
