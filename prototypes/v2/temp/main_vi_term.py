# main_vi_term.py
# Clean, stable version with horizontal bottom split: TERM | OUT

import sys
import curses
import subprocess
import pandas as pd

# ---------------- table helpers ----------------

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


def draw_table(win, headers, rows, max_rows, active=False):
    win.erase()
    h, w = win.getmaxyx()
    max_width = w - 2
    lines = format_table(headers, rows, max_width)
    for i, line in enumerate(lines[:max_rows]):
        try:
            win.addnstr(i + 1, 1, line, max_width)
        except curses.error:
            pass
    win.box()
    if active:
        label = " DF "
        win.addnstr(h - 2, max(1, w - len(label) - 2), label, len(label))
    win.refresh()

# ---------------- editor helpers ----------------

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


def draw_editor(win, buffer, cursor, mode, active=False):
    win.erase()
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
        try:
            win.addnstr(r + 1, 1, line, w - 2)
        except curses.error:
            pass

    if active:
        status = f" TERM:{mode.upper()} "
        win.addnstr(h - 2, max(1, w - len(status) - 2), status, len(status))
        cy = max(1, min(1 + cur_row, h - 2))
        cx = max(1, min(1 + cur_col, w - 2))
        win.move(cy, cx)

    win.box()
    win.refresh()


def draw_output(win, lines, active=False):
    win.erase()
    h, w = win.getmaxyx()
    for i, line in enumerate(lines[: h - 2]):
        try:
            win.addnstr(i + 1, 1, line, w - 2)
        except curses.error:
            pass
    win.box()
    if active:
        label = " OUT "
        win.addnstr(h - 2, max(1, w - len(label) - 2), label, len(label))
    win.refresh()

# ---------------- main ----------------

def curses_main(stdscr, df):
    curses.curs_set(1)
    stdscr.clear()
    stdscr.refresh()

    H, W = stdscr.getmaxyx()
    input_h = max(6, H * 2 // 5)
    table_h = H - input_h

    table_win = curses.newwin(table_h, W, 0, 0)
    bottom_win = curses.newwin(input_h, W, table_h, 0)

    # horizontal split: TERM | OUT
    left_w = W // 2
    right_w = W - left_w
    term_win = bottom_win.derwin(input_h, left_w, 0, 0)
    out_win = bottom_win.derwin(input_h, right_w, 0, left_w)

    buffer = ""
    cursor = 0
    mode = "insert"
    history = []
    hist_idx = -1
    output_lines = []

    focus = 1  # 0=df, 1=terminal, 2=output
    df_scroll = 0
    out_scroll = 0

    # ---- initial render so UI appears immediately (TERM last so cursor is correct) ----
    draw_table(table_win, list(df.columns), df.values.tolist(), table_h - 2, active=False)
    draw_output(out_win, output_lines, active=False)
    draw_editor(term_win, buffer, cursor, mode, active=True)

    while True:
        ch = stdscr.getch()

        # cycle focus
        if ch == 23:  # Ctrl+W
            focus = (focus + 1) % 3
            # redraw immediately so focus indicator updates
            draw_table(table_win, list(df.columns), df.values.tolist()[df_scroll:], table_h - 2, active=(focus == 0))
            draw_output(out_win, output_lines[out_scroll:], active=(focus == 2))
            draw_editor(term_win, buffer, cursor, mode, active=(focus == 1))
            continue

        if mode == "insert":
            if ch == 27:
                mode = "normal"
                continue

            if ch == 5:  # Ctrl+E
                cmd = buffer.strip()
                if cmd:
                    history.append(cmd)
                    hist_idx = len(history)
                    try:
                        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                        output_lines = res.stdout.splitlines() + res.stderr.splitlines()
                    except Exception as e:
                        output_lines = [str(e)]

                # --- immediate redraw so output appears instantly ---
                draw_table(
                    table_win,
                    list(df.columns),
                    df.values.tolist()[df_scroll:],
                    table_h - 2,
                    active=(focus == 0),
                )
                draw_output(out_win, output_lines[out_scroll:], active=(focus == 2))

                # --- force visible cursor back to TERM ---
                try:
                    row, col, _ = cursor_to_rowcol(buffer, cursor)
                    cy = max(1, min(1 + row, term_win.getmaxyx()[0] - 2))
                    cx = max(1, min(1 + col, term_win.getmaxyx()[1] - 2))
                    term_win.move(cy, cx)
                    term_win.refresh()
                except curses.error:
                    pass

                continue

            if focus != 1:
                continue

            if ch in (curses.KEY_BACKSPACE, 127):
                if cursor > 0:
                    buffer = buffer[: cursor - 1] + buffer[cursor:]
                    cursor -= 1
            elif ch == 10:
                buffer = buffer[:cursor] + "\n" + buffer[cursor:]
                cursor += 1
            elif 32 <= ch <= 126:
                buffer = buffer[:cursor] + chr(ch) + buffer[cursor:]
                cursor += 1

        else:  # NORMAL mode
            if focus == 0:
                if ch == ord('j'):
                    df_scroll = min(len(df) - 1, df_scroll + 1)
                elif ch == ord('k'):
                    df_scroll = max(0, df_scroll - 1)
                continue

            if focus == 2:
                if ch == ord('j'):
                    out_scroll = min(len(output_lines) - 1, out_scroll + 1)
                elif ch == ord('k'):
                    out_scroll = max(0, out_scroll - 1)
                continue

            if ch == ord('i'):
                mode = "insert"
            elif ch == 27:
                break
            else:
                cursor = handle_motion(ch, buffer, cursor)

        # redraw (TERM last so it owns the cursor)
        draw_table(table_win, list(df.columns), df.values.tolist()[df_scroll:], table_h - 2, active=(focus == 0))
        draw_output(out_win, output_lines[out_scroll:], active=(focus == 2))
        draw_editor(term_win, buffer, cursor, mode, active=(focus == 1))


def main():
    if len(sys.argv) != 2:
        print("Usage: python main_vi_term.py <csv_file>")
        sys.exit(1)
    df = pd.read_csv(sys.argv[1])
    curses.wrapper(curses_main, df)


if __name__ == "__main__":
    main()
