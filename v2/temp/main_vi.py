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


# -------- vim word motions --------

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


def delete_to(buf, cur, new_cur):
    if new_cur > cur:
        return buf[:cur] + buf[new_cur:], cur
    else:
        return buf[:new_cur] + buf[cur:], new_cur


# ----------------------------------

def draw_input(win, buffer, cursor, mode):
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

    for r, line in enumerate(lines[: h - 2]):
        win.addstr(r + 1, 1, line[: w - 2])

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
    mode = "normal"
    pending = None  # for commands like c?, d?

    draw_table(table_win, headers, rows, table_h - 2)
    draw_input(input_win, buffer, cursor, mode)

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

        else:  # NORMAL MODE
            if pending:
                if pending in ('d', 'c'):
                    if ch == ord('w'):
                        new = move_word_forward(buffer, cursor)
                        buffer, cursor = delete_to(buffer, cursor, new)
                        if pending == 'c':
                            mode = 'insert'
                pending = None

            elif ch in (ord('d'), ord('c')):
                pending = chr(ch)

            elif ch == ord('w'):
                cursor = move_word_forward(buffer, cursor)
            elif ch == ord('b'):
                cursor = move_word_backward(buffer, cursor)
            elif ch == ord('i'):
                mode = "insert"
            elif ch == ord('h'):
                cursor = max(0, cursor - 1)
            elif ch == ord('l'):
                cursor = min(len(buffer), cursor + 1)
            elif ch == ord('k'):
                row, col, lines = cursor_to_rowcol(buffer, cursor)
                if row > 0:
                    cursor = rowcol_to_cursor(lines, row - 1, col)
            elif ch == ord('j'):
                row, col, lines = cursor_to_rowcol(buffer, cursor)
                if row < len(lines) - 1:
                    cursor = rowcol_to_cursor(lines, row + 1, col)
            elif ch == ord('0'):
                row, col, lines = cursor_to_rowcol(buffer, cursor)
                cursor = rowcol_to_cursor(lines, row, 0)
            elif ch == ord('$'):
                row, col, lines = cursor_to_rowcol(buffer, cursor)
                cursor = rowcol_to_cursor(lines, row, len(lines[row]))
            elif ch == ord('x'):
                if cursor < len(buffer):
                    buffer = buffer[:cursor] + buffer[cursor + 1:]
            elif ch == 27:
                break

        draw_input(input_win, buffer, cursor, mode)


def main():
    if len(sys.argv) != 2:
        print("Usage: python main_vi.py <csv_file>")
        sys.exit(1)
    df = pd.read_csv(sys.argv[1])
    curses.wrapper(curses_main, df)


if __name__ == "__main__":
    main()
