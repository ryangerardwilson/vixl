import curses
from typing import List


class OverlayView:
    def __init__(self, layout):
        self.layout = layout
        self.visible = False
        self.lines: List[str] = []
        self.scroll = 0
        self.win = None
        self.leader_pending = False

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
        self.leader_pending = False

    def close(self):
        self.visible = False
        self.lines = []
        self.scroll = 0
        self.win = None
        self.leader_pending = False

    def handle_key(self, ch):
        if not self.visible:
            return
        if ch == -1:
            return

        max_visible = max(0, self.layout.overlay_h - 2)
        max_scroll = max(0, len(self.lines) - max_visible)
        half_page = max(1, max_visible // 2)

        # leader handling (,j / ,k)
        if self.leader_pending:
            if ch == ord(","):
                self.leader_pending = False
                return

            if ch in (ord("j"), curses.KEY_DOWN):
                self.scroll = max_scroll
                self.leader_pending = False
                return

            if ch in (ord("k"), curses.KEY_UP):
                self.scroll = 0
                self.leader_pending = False
                return

            # non-matching key cancels leader
            self.leader_pending = False
            return

        # close
        if ch in (27, ord("q"), 13, curses.KEY_ENTER):
            self.close()
            return

        # start leader
        if ch == ord(","):
            self.leader_pending = True
            return

        # half-page scroll
        if ch == 10:  # Ctrl+J
            self.scroll = min(max_scroll, self.scroll + half_page)
            return
        if ch == 11:  # Ctrl+K
            self.scroll = max(0, self.scroll - half_page)
            return

        # line scroll
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
