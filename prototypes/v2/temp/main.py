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


def draw_input(win, buffer, cursor):
    win.erase()
    win.box()
    h, w = win.getmaxyx()
    lines = buffer.split("\n")

    # determine cursor row/col
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

    cy = max(1, min(1 + cur_row, h - 2))
    cx = max(1, min(1 + cur_col, w - 2))
    win.move(cy, cx)
    win.refresh()


# ---------- editor movement helpers ----------

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


# ---------------------------------------------

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
    preferred_col = 0

    draw_table(table_win, headers, rows, table_h - 2)
    draw_input(input_win, buffer, cursor)

    while True:
        ch = stdscr.getch()

        # Meta (Alt) handling
        if ch == 27:
            stdscr.nodelay(True)
            nxt = stdscr.getch()
            stdscr.nodelay(False)
            if nxt == -1:
                break
            if nxt in (ord('b'), ord('B')):
                while cursor > 0 and buffer[cursor - 1].isspace():
                    cursor -= 1
                while cursor > 0 and not buffer[cursor - 1].isspace():
                    cursor -= 1
            elif nxt in (ord('f'), ord('F')):
                while cursor < len(buffer) and not buffer[cursor].isspace():
                    cursor += 1
                while cursor < len(buffer) and buffer[cursor].isspace():
                    cursor += 1
            preferred_col = cursor_to_rowcol(buffer, cursor)[1]
            draw_input(input_win, buffer, cursor)
            continue

        row, col, lines = cursor_to_rowcol(buffer, cursor)

        if ch in (curses.KEY_UP, 16):  # Up / Ctrl-P
            if row > 0:
                cursor = rowcol_to_cursor(lines, row - 1, preferred_col)
        elif ch in (curses.KEY_DOWN, 14):  # Down / Ctrl-N
            if row < len(lines) - 1:
                cursor = rowcol_to_cursor(lines, row + 1, preferred_col)
        elif ch in (curses.KEY_LEFT, 2):  # Left / Ctrl-B
            cursor = max(0, cursor - 1)
            preferred_col = cursor_to_rowcol(buffer, cursor)[1]
        elif ch in (curses.KEY_RIGHT, 6):  # Right / Ctrl-F
            cursor = min(len(buffer), cursor + 1)
            preferred_col = cursor_to_rowcol(buffer, cursor)[1]
        elif ch == 1:  # Ctrl-A
            cursor = rowcol_to_cursor(lines, row, 0)
            preferred_col = 0
        elif ch == 5:  # Ctrl-E
            cursor = rowcol_to_cursor(lines, row, len(lines[row]))
            preferred_col = len(lines[row])
        elif ch in (curses.KEY_BACKSPACE, 127):
            if cursor > 0:
                buffer = buffer[: cursor - 1] + buffer[cursor:]
                cursor -= 1
                preferred_col = cursor_to_rowcol(buffer, cursor)[1]
        elif ch == 10:
            buffer = buffer[:cursor] + "\n" + buffer[cursor:]
            cursor += 1
            preferred_col = 0
        elif 32 <= ch <= 126:
            buffer = buffer[:cursor] + chr(ch) + buffer[cursor:]
            cursor += 1
            preferred_col = cursor_to_rowcol(buffer, cursor)[1]

        draw_input(input_win, buffer, cursor)


def main():
    if len(sys.argv) != 2:
        print("Usage: python main.py <csv_file>")
        sys.exit(1)
    df = pd.read_csv(sys.argv[1])
    curses.wrapper(curses_main, df)


if __name__ == "__main__":
    main()
