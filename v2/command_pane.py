import curses


class CommandPane:
    def __init__(self):
        self.buffer = ""
        self.cursor = 0
        self.mode = "insert"  # insert | normal

    # ---------- cursor helpers ----------
    def _cursor_to_rowcol(self):
        lines = self.buffer.split("\n")
        idx = 0
        for r, line in enumerate(lines):
            if idx + len(line) >= self.cursor:
                return r, self.cursor - idx, lines
            idx += len(line) + 1
        return len(lines) - 1, len(lines[-1]), lines

    def _rowcol_to_cursor(self, lines, row, col):
        idx = 0
        for r in range(row):
            idx += len(lines[r]) + 1
        return idx + min(col, len(lines[row]))

    # ---------- motions ----------
    def _move_word_forward(self):
        buf = self.buffer
        i = self.cursor
        n = len(buf)
        while i < n and buf[i].isspace():
            i += 1
        while i < n and not buf[i].isspace():
            i += 1
        self.cursor = i

    def _move_word_backward(self):
        buf = self.buffer
        i = max(0, self.cursor - 1)
        while i > 0 and buf[i].isspace():
            i -= 1
        while i > 0 and not buf[i - 1].isspace():
            i -= 1
        self.cursor = i

    def handle_motion(self, ch):
        if ch == ord('h'):
            self.cursor = max(0, self.cursor - 1)
        elif ch == ord('l'):
            self.cursor = min(len(self.buffer), self.cursor + 1)
        elif ch == ord('w'):
            self._move_word_forward()
        elif ch == ord('b'):
            self._move_word_backward()
        elif ch == ord('0'):
            row, col, lines = self._cursor_to_rowcol()
            self.cursor = self._rowcol_to_cursor(lines, row, 0)
        elif ch == ord('$'):
            row, col, lines = self._cursor_to_rowcol()
            self.cursor = self._rowcol_to_cursor(lines, row, len(lines[row]))
        elif ch == ord('k'):
            row, col, lines = self._cursor_to_rowcol()
            if row > 0:
                self.cursor = self._rowcol_to_cursor(lines, row - 1, col)
        elif ch == ord('j'):
            row, col, lines = self._cursor_to_rowcol()
            if row < len(lines) - 1:
                self.cursor = self._rowcol_to_cursor(lines, row + 1, col)

    # ---------- input ----------
    def handle_key(self, ch):
        if self.mode == "insert":
            if ch == 27:  # ESC
                self.mode = "normal"
                return None
            if ch in (curses.KEY_BACKSPACE, 127):
                if self.cursor > 0:
                    self.buffer = self.buffer[: self.cursor - 1] + self.buffer[self.cursor :]
                    self.cursor -= 1
            elif ch == 10:  # Enter
                self.buffer = self.buffer[: self.cursor] + "\n" + self.buffer[self.cursor :]
                self.cursor += 1
            elif 32 <= ch <= 126:
                self.buffer = self.buffer[: self.cursor] + chr(ch) + self.buffer[self.cursor :]
                self.cursor += 1
        else:
            if ch == ord('i'):
                self.mode = "insert"
            else:
                self.handle_motion(ch)
        return None

    # ---------- execution helpers ----------
    def get_buffer(self):
        return self.buffer

    def reset(self):
        self.buffer = ""
        self.cursor = 0
        self.mode = "insert"

    # ---------- rendering ----------
    def draw(self, win, active=False):
        win.erase()
        h, w = win.getmaxyx()
        lines = self.buffer.split("\n")

        # draw text
        for r, line in enumerate(lines[: h - 2]):
            try:
                win.addnstr(r + 1, 1, line, w - 2)
            except curses.error:
                pass

        if active:
            status = f" CMD:{self.mode.upper()} "
            win.addnstr(h - 2, max(1, w - len(status) - 2), status, len(status))
            row, col, _ = self._cursor_to_rowcol()
            cy = max(1, min(1 + row, h - 2))
            cx = max(1, min(1 + col, w - 2))
            try:
                win.move(cy, cx)
            except curses.error:
                pass

        win.box()
        win.refresh()