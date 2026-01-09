import curses


class CommandPane:
    def __init__(self):
        self.buffer = ""
        self.cursor = 0
        self.mode = "normal"  # normal | insert | visual
        self.scroll = 0
        self.hscroll = 0
        self.yank = ""
        self.visual_start = None

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
            if ch == 9:  # Tab -> indent
                self.buffer = self.buffer[: self.cursor] + "    " + self.buffer[self.cursor :]
                self.cursor += 4
            elif ch in (curses.KEY_BACKSPACE, 127):
                if self.cursor > 0:
                    self.buffer = self.buffer[: self.cursor - 1] + self.buffer[self.cursor :]
                    self.cursor -= 1
            elif ch == 10:  # Enter
                self.buffer = self.buffer[: self.cursor] + "\n" + self.buffer[self.cursor :]
                self.cursor += 1
            elif 32 <= ch <= 126:
                self.buffer = self.buffer[: self.cursor] + chr(ch) + self.buffer[self.cursor :]
                self.cursor += 1
        elif self.mode == "visual":
            # visual mode operations
            if ch == 27:  # ESC
                self.mode = "normal"
                self.visual_start = None
                return None

            # motions reuse normal motions
            if ch in (ord('h'), ord('l'), ord('j'), ord('k'), ord('w'), ord('b')):
                self.handle_motion(ch)
                return None

            if self.visual_start is None:
                return None
            start = min(self.visual_start, self.cursor)
            end = max(self.visual_start, self.cursor)

            if ch == ord('y'):
                self.yank = self.buffer[start:end]
                self.mode = "normal"
                self.visual_start = None
                return None

            if ch == ord('d'):
                self.yank = self.buffer[start:end]
                self.buffer = self.buffer[:start] + self.buffer[end:]
                self.cursor = start
                self.mode = "normal"
                self.visual_start = None
                return None

            if ch == ord('p'):
                if self.yank:
                    self.buffer = self.buffer[:start] + self.yank + self.buffer[end:]
                    self.cursor = start + len(self.yank)
                self.mode = "normal"
                self.visual_start = None
                return None

        else:
            # ----- operator-pending resolution FIRST -----
            if getattr(self, '_pending', None) == 'd' and ch == ord('d'):
                # dd: delete (and yank) current line
                row, col, lines = self._cursor_to_rowcol()
                if lines:
                    self.yank = lines[row] + "\n"
                    lines.pop(row)
                    self.buffer = "\n".join(lines)
                    if lines:
                        new_row = min(row, len(lines) - 1)
                        self.cursor = self._rowcol_to_cursor(lines, new_row, 0)
                    else:
                        self.cursor = 0
                self._pending = None
                return None

            if getattr(self, '_pending', None) == 'd' and ch == ord('w'):
                start = self.cursor
                self._move_word_forward()
                end = self.cursor
                # do not consume trailing quote
                if end > start and self.buffer[end - 1] in ("'", '"'):
                    end -= 1
                self.buffer = self.buffer[:start] + self.buffer[end:]
                self.cursor = start
                self._pending = None
                return None

            if getattr(self, '_pending', None) == 'c' and ch == ord('w'):
                start = self.cursor
                self._move_word_forward()
                end = self.cursor
                # do not consume trailing quote
                if end > start and self.buffer[end - 1] in ("'", '"'):
                    end -= 1
                self.buffer = self.buffer[:start] + self.buffer[end:]
                self.cursor = start
                self.mode = "insert"
                self._pending = None
                return None

            # ----- normal mode commands -----
            # resolve leader sequences first
            if getattr(self, '_pending', None) == ',' and ch == ord('e'):
                # ,e -> append at end of line (like Vim A)
                row, col, lines = self._cursor_to_rowcol()
                self.cursor = self._rowcol_to_cursor(lines, row, len(lines[row]))
                self.mode = "insert"
                self._pending = None
                return None

            if getattr(self, '_pending', None) == ',' and ch == ord('j'):
                # ,j -> jump to last line
                lines = self.buffer.split("\n")
                if lines:
                    self.cursor = self._rowcol_to_cursor(lines, len(lines) - 1, 0)
                self._pending = None
                return None

            if getattr(self, '_pending', None) == ',' and ch == ord('k'):
                # ,k -> jump to first line
                lines = self.buffer.split("\n")
                if lines:
                    self.cursor = self._rowcol_to_cursor(lines, 0, 0)
                self._pending = None
                return None

            self._pending = None

            # leader key ','
            if ch == ord(','):
                self._pending = ','
                return None

            if ch == ord('i'):
                self.mode = "insert"
            elif ch == ord('r'):
                # replace single character
                self._pending = 'r'
                return None
            elif ch == ord('v'):
                self.mode = "visual"
                self.visual_start = self.cursor
            elif ch == ord('j'):
                row, col, lines = self._cursor_to_rowcol()
                if row < len(lines) - 1:
                    self.cursor = self._rowcol_to_cursor(lines, row + 1, col)
            elif ch == ord('k'):
                row, col, lines = self._cursor_to_rowcol()
                if row > 0:
                    self.cursor = self._rowcol_to_cursor(lines, row - 1, col)
            elif getattr(self, '_pending', None) == 'r':
                # r<char>: replace char under cursor
                if self.cursor < len(self.buffer) and 32 <= ch <= 126:
                    self.buffer = (
                        self.buffer[: self.cursor]
                        + chr(ch)
                        + self.buffer[self.cursor + 1 :]
                    )
                self._pending = None
                return None
            elif ch == ord('w'):
                self._move_word_forward()
            elif ch == ord('p'):
                # paste after cursor/line
                if self.yank:
                    row, col, lines = self._cursor_to_rowcol()
                    insert_at = row + 1
                    new_lines = self.buffer.split("\n")
                    new_lines.insert(insert_at, self.yank.rstrip("\n"))
                    self.buffer = "\n".join(new_lines)
                    self.cursor = self._rowcol_to_cursor(new_lines, insert_at, 0)
            elif ch == ord('b'):
                self._move_word_backward()
            elif ch == ord('d'):
                self._pending = 'd'
            elif ch == ord('c'):
                self._pending = 'c'
            elif getattr(self, '_pending', None) == ',' and ch == ord('e'):
                # ,e -> append at end of line (like Vim A)
                row, col, lines = self._cursor_to_rowcol()
                self.cursor = self._rowcol_to_cursor(lines, row, len(lines[row]))
                self.mode = "insert"
                self._pending = None
            else:
                self.handle_motion(ch)
        return None

    # ---------- execution helpers ----------
    def get_buffer(self):
        return self.buffer

    def set_buffer(self, text):
        self.buffer = text
        self.cursor = len(text)
        self.mode = "normal"

    def reset(self):
        self.buffer = ""
        self.cursor = 0
        self.mode = "insert"

    # ---------- rendering ----------
    def draw(self, win, active=False):
        win.erase()
        h, w = win.getmaxyx()
        lines = self.buffer.split("\n")
        line_no_width = max(3, len(str(len(lines))) + 1)

        max_visible = h - 2
        if self.scroll > max(0, len(lines) - max_visible):
            self.scroll = max(0, len(lines) - max_visible)

        visible = lines[self.scroll : self.scroll + max_visible]

        text_w = w - (line_no_width + 3)
        for i, line in enumerate(visible):
            ln = self.scroll + i + 1
            row_idx = self.scroll + i
            slice_start = self.hscroll
            slice_end = slice_start + text_w
            try:
                win.addnstr(i + 1, 1, f"{ln:>{line_no_width}} ", line_no_width + 1, curses.A_DIM)

                # draw line with optional visual selection
                if self.mode == "visual" and self.visual_start is not None:
                    start = min(self.visual_start, self.cursor)
                    end = max(self.visual_start, self.cursor)

                    line_start = sum(len(l) + 1 for l in lines[:row_idx])

                    for j, ch in enumerate(line[slice_start:slice_end]):
                        abs_idx = line_start + slice_start + j
                        attr = curses.A_REVERSE if start <= abs_idx < end else 0
                        win.addch(i + 1, 1 + line_no_width + 1 + j, ch, attr)
                else:
                    win.addnstr(
                        i + 1,
                        1 + line_no_width + 1,
                        line[slice_start:slice_end],
                        text_w,
                    )
            except curses.error:
                pass

        if active:
            status = f" CMD:{self.mode.upper()} "
            win.addnstr(h - 2, max(1, w - len(status) - 2), status, len(status))
            row, col, _ = self._cursor_to_rowcol()
            if row < self.scroll:
                self.scroll = row
            elif row >= self.scroll + max_visible:
                self.scroll = row - max_visible + 1
            # horizontal scroll to keep cursor visible
            text_w = w - (line_no_width + 3)
            if col < self.hscroll:
                self.hscroll = col
            elif col >= self.hscroll + text_w:
                self.hscroll = col - text_w + 1

            cy = 1 + (row - self.scroll)
            cx = 1 + line_no_width + 1 + (col - self.hscroll)
            try:
                win.move(cy, max(1 + line_no_width + 1, min(cx, w - 2)))
            except curses.error:
                pass

        win.refresh()