import curses
from typing import Optional, Callable


class SavePrompt:
    def __init__(self, state, file_type_handler_cls, set_status_cb: Callable[[str, int], None]):
        self.state = state
        self.FileTypeHandler = file_type_handler_cls
        self._set_status = set_status_cb

        self.active = False
        self.buffer = ""
        self.cursor = 0
        self.hscroll = 0
        self.save_and_exit = False
        self.exit_requested = False

    def start(self, current_path: Optional[str], save_and_exit: bool = False):
        self.active = True
        self.buffer = current_path or ''
        self.cursor = len(self.buffer)
        self.hscroll = 0
        self.save_and_exit = save_and_exit
        self.exit_requested = False

    def handle_key(self, ch):
        if not self.active:
            return

        if ch in (10, 13):  # Enter
            path = self.buffer.strip()
            if not path:
                self._set_status("Path required", 3)
                return
            if not (path.lower().endswith('.csv') or path.lower().endswith('.parquet')):
                self._set_status("Save failed: use .csv or .parquet", 4)
                return
            try:
                handler = self.FileTypeHandler(path)
                if hasattr(self.state, 'ensure_non_empty'):
                    self.state.ensure_non_empty()
                handler.save(self.state.df)
                self.state.file_handler = handler
                self.state.file_path = path
                self._set_status(f"Saved {path}", 3)
                self.active = False
                self.buffer = ""
                self.cursor = 0
                self.hscroll = 0
                if self.save_and_exit:
                    self.exit_requested = True
                self.save_and_exit = False
            except Exception as e:
                msg = f"Save failed: {e}"
                self._set_status(msg, 4)
            return

        if ch == 27:  # Esc
            self.active = False
            self.save_and_exit = False
            self.buffer = ""
            self.cursor = 0
            self.hscroll = 0
            self._set_status("Save canceled", 3)
            return

        if ch in (curses.KEY_BACKSPACE, 127, 8):
            if self.cursor > 0:
                self.buffer = self.buffer[: self.cursor - 1] + self.buffer[self.cursor :]
                self.cursor -= 1
            return

        if ch == curses.KEY_LEFT:
            self.cursor = max(0, self.cursor - 1)
            return

        if ch == curses.KEY_RIGHT:
            self.cursor = min(len(self.buffer), self.cursor + 1)
            return

        if ch == curses.KEY_HOME:
            self.cursor = 0
            return

        if ch == curses.KEY_END:
            self.cursor = len(self.buffer)
            return

        if 32 <= ch <= 126:
            self.buffer = self.buffer[: self.cursor] + chr(ch) + self.buffer[self.cursor :]
            self.cursor += 1
            return

    def draw(self, win):
        prompt = "Save as: "
        h, w = win.getmaxyx()
        text_w = max(1, w - len(prompt) - 1)

        # adjust hscroll
        if self.cursor < self.hscroll:
            self.hscroll = self.cursor
        elif self.cursor > self.hscroll + text_w:
            self.hscroll = self.cursor - text_w

        start = self.hscroll
        end = start + text_w
        visible = self.buffer[start:end]

        try:
            win.addnstr(0, 0, prompt, len(prompt))
            win.addnstr(0, len(prompt), visible, text_w)
            win.move(0, len(prompt) + (self.cursor - self.hscroll))
        except curses.error:
            pass
        win.refresh()
