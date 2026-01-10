import curses


class CommandPane:
    def __init__(self):
        self.buffer = ""
        self.cursor = 0
        self.hscroll = 0
        self.active = False
        self.history = []
        self.history_idx = None  # None means not navigating history

    # ---------- state helpers ----------
    def reset(self):
        self.buffer = ""
        self.cursor = 0
        self.hscroll = 0
        self.active = False
        self.history_idx = None

    def activate(self):
        self.active = True
        self.cursor = len(self.buffer)
        self.history_idx = None

    def get_buffer(self):
        return self.buffer

    def set_buffer(self, text):
        self.buffer = text or ""
        self.cursor = len(self.buffer)
        self.hscroll = 0
        self.history_idx = None

    def set_history(self, entries):
        self.history = list(entries or [])
        self.history_idx = None

    def _apply_history(self):
        if self.history_idx is None:
            return
        if 0 <= self.history_idx < len(self.history):
            self.buffer = self.history[self.history_idx]
        else:
            self.buffer = ""
        self.cursor = len(self.buffer)
        self.hscroll = 0

    # ---------- input handling ----------
    def handle_key(self, ch):
        if not self.active:
            return None

        # history navigation
        if ch == 16:  # Ctrl+P
            if self.history:
                if self.history_idx is None:
                    self.history_idx = len(self.history) - 1
                else:
                    self.history_idx = max(0, self.history_idx - 1)
                self._apply_history()
            return None
        if ch == 14:  # Ctrl+N
            if self.history:
                if self.history_idx is None:
                    # stay at blank
                    self.buffer = ""
                    self.cursor = 0
                    self.hscroll = 0
                else:
                    self.history_idx += 1
                    if self.history_idx >= len(self.history):
                        self.history_idx = None
                        self.buffer = ""
                        self.cursor = 0
                        self.hscroll = 0
                    else:
                        self._apply_history()
            return None

        # submit
        if ch in (10, 13, 5):  # Enter or Ctrl+E
            return "submit"

        # cancel
        if ch == 27:  # Esc
            self.reset()
            return "cancel"

        if ch in (curses.KEY_BACKSPACE, 127, 8):
            if self.cursor > 0:
                self.buffer = self.buffer[: self.cursor - 1] + self.buffer[self.cursor :]
                self.cursor -= 1
            self.history_idx = None
            return None

        if ch == curses.KEY_LEFT:
            self.cursor = max(0, self.cursor - 1)
            return None

        if ch == curses.KEY_RIGHT:
            self.cursor = min(len(self.buffer), self.cursor + 1)
            return None

        if ch == curses.KEY_HOME:
            self.cursor = 0
            return None

        if ch == curses.KEY_END:
            self.cursor = len(self.buffer)
            return None

        if 32 <= ch <= 126:
            self.buffer = self.buffer[: self.cursor] + chr(ch) + self.buffer[self.cursor :]
            self.cursor += 1
            self.history_idx = None
            return None

        return None

    # ---------- rendering ----------
    def draw(self, win, active=False):
        win.erase()
        h, w = win.getmaxyx()
        prompt = ":"
        text_w = max(1, w - len(prompt) - 1)

        # adjust scroll to keep cursor visible
        if self.cursor < self.hscroll:
            self.hscroll = self.cursor
        elif self.cursor > self.hscroll + text_w:
            self.hscroll = self.cursor - text_w

        slice_start = self.hscroll
        slice_end = slice_start + text_w
        visible = self.buffer[slice_start:slice_end]

        try:
            win.addnstr(0, 0, prompt, len(prompt))
            win.addnstr(0, len(prompt), visible, text_w)
        except curses.error:
            pass

        if active and self.active:
            cx = len(prompt) + (self.cursor - self.hscroll)
            cy = 0
            try:
                win.move(cy, max(0, min(cx, w - 1)))
            except curses.error:
                pass

        win.refresh()
