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


def draw_input(win, buffer):
    win.erase()
    win.box()
    win.addstr(1, 1, buffer[: win.getmaxyx()[1] - 3])
    win.refresh()


def curses_main(stdscr, df):
    curses.curs_set(1)
    stdscr.clear()
    stdscr.refresh()

    height, width = stdscr.getmaxyx()
    table_h = height - 3

    table_win = curses.newwin(table_h, width, 0, 0)
    input_win = curses.newwin(3, width, table_h, 0)

    headers = list(df.columns)
    rows = df.values.tolist()
    buffer = ""

    # ✅ Force initial render BEFORE input
    draw_table(table_win, headers, rows, table_h - 2)
    draw_input(input_win, buffer)

    while True:
        ch = stdscr.getch()

        if ch == 27:  # ESC
            break
        elif ch in (curses.KEY_BACKSPACE, 127):
            buffer = buffer[:-1]
        elif ch == 10:  # Enter
            buffer = ""
        elif 32 <= ch <= 126:
            buffer += chr(ch)

        draw_input(input_win, buffer)


def main():
    if len(sys.argv) != 2:
        print("Usage: python main.py <csv_file>")
        sys.exit(1)

    df = pd.read_csv(sys.argv[1])
    curses.wrapper(curses_main, df)


if __name__ == "__main__":
    main()
