import curses
from typing import List


class OverlayView:
    def __init__(self, layout):
        self.layout = layout
        self.visible = False
        self.lines: List[str] = []
        self.scroll = 0
        self.win = None

    def open(self, lines: List[str]):
        max_h = min(self.layout.H // 2, self.layout.H - 2)
        content_h = len(lines) + 2  # box padding
        overlay_h = max(3, min(content_h, max_h))
        overlay_y = max(0, (self.layout.table_h - overlay_h) // 2)

        self.layout.overlay_h = overlay_h
        self.win = curses.newwin(overlay_h, self.layout.W, overlay_y, 0)
        self.win.leaveok(True)

        self.lines = lines
        self.scroll = 0
        self.visible = True

    def close(self):
        self.visible = False
        self.lines = []
        self.scroll = 0
        self.win = None

    def handle_key(self, ch):
        if not self.visible:
            return
        max_visible = max(0, self.layout.overlay_h - 2)
        max_scroll = max(0, len(self.lines) - max_visible)

        if ch in (27, ord("q"), 10, 13):
            self.close()
            return
        if ch == ord("j"):
            self.scroll = min(max_scroll, self.scroll + 1)
        elif ch == ord("k"):
            self.scroll = max(0, self.scroll - 1)

    def draw(self):
        if not self.visible or not self.win:
            return
        win = self.win
        win.erase()
        h, w = win.getmaxyx()
        win.box()

        max_visible = max(0, h - 2)
        start = self.scroll
        end = start + max_visible
        for i, line in enumerate(self.lines[start:end]):
            try:
                win.addnstr(1 + i, 1, line, w - 2)
            except curses.error:
                pass

        win.refresh()
