class OutputPane:
    def __init__(self):
        self.lines = []
        self.scroll = 0

    def set_lines(self, lines):
        self.lines = lines
        self.scroll = 0

    def scroll_down(self):
        self.scroll = min(len(self.lines) - 1, self.scroll + 1)

    def scroll_up(self):
        self.scroll = max(0, self.scroll - 1)

    def draw(self, win, active=False):
        win.erase()
        h, w = win.getmaxyx()
        for i, line in enumerate(self.lines[self.scroll :][: h - 2]):
            try:
                win.addnstr(i + 1, 1, line, w - 2)
            except Exception:
                pass
        if active:
            win.addnstr(h - 2, w - 9, " OUT ", 7)
        win.box()
        win.refresh()