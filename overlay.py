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
        self.mode: str | None = None

    def open_help(self, lines: List[str]):
        self._open(lines, mode="help")

    def open_output(self, lines: List[str]):
        self._open(lines, mode="output")

    def _open(self, lines: List[str], *, mode: str):
        if not isinstance(lines, list):
            lines = list(lines or [])

        self.mode = mode
        self.lines = lines
        self.scroll = 0
        self.leader_pending = False

        if mode == "help":
            overlay_h = max(3, self.layout.H)
            overlay_y = 0
        else:
            max_h = min(self.layout.H // 2, self.layout.H - 2)
            content_h = len(lines) + 2  # box padding
            overlay_h = max(3, min(content_h, max_h))
            overlay_y = max(0, (self.layout.table_h - overlay_h) // 2)

        self.layout.overlay_h = overlay_h
        self.win = curses.newwin(overlay_h, self.layout.W, overlay_y, 0)
        self.win.leaveok(True)

        self.visible = True

    def close(self):
        self.visible = False
        self.lines = []
        self.scroll = 0
        self.win = None
        self.leader_pending = False
        self.mode = None

    def handle_key(self, ch):
        if not self.visible or self.win is None:
            return
        if ch == -1:
            return

        h, _ = self.win.getmaxyx()
        if self.mode == "help":
            content_rows = max(0, h)
        else:
            content_rows = max(0, h - 2)

        max_scroll = max(0, len(self.lines) - content_rows)
        half_page = max(1, content_rows // 2)

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
        if ch in (27, ord("q"), 13, curses.KEY_ENTER, ord("?")):
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

        if ch == curses.KEY_NPAGE:
            self.scroll = min(max_scroll, self.scroll + half_page)
            return
        if ch == curses.KEY_PPAGE:
            self.scroll = max(0, self.scroll - half_page)
            return

        if ch == curses.KEY_HOME:
            self.scroll = 0
            return
        if ch == curses.KEY_END:
            self.scroll = max_scroll
            return

        # line scroll
        if ch in (ord("j"), curses.KEY_DOWN):
            self.scroll = min(max_scroll, self.scroll + 1)
        elif ch in (ord("k"), curses.KEY_UP):
            self.scroll = max(0, self.scroll - 1)

    def draw(self):
        if not self.visible or not self.win:
            return

        if self.mode == "help":
            self._draw_help()
        else:
            self._draw_output()

    def _draw_help(self):
        if not self.win:
            return

        win = self.win
        win.erase()
        h, w = win.getmaxyx()

        dim_attr = curses.A_DIM if hasattr(curses, "A_DIM") else 0
        blank = " " * max(1, w - 1)
        for row in range(max(0, h)):
            try:
                win.addnstr(row, 0, blank, w - 1, dim_attr)
            except curses.error:
                pass

        max_visible = max(0, h)
        start = self.scroll
        end = start + max_visible
        for idx, line in enumerate(self.lines[start:end]):
            try:
                win.addnstr(idx, 0, line.ljust(w - 1), w - 1)
            except curses.error:
                pass

        win.refresh()

    def _draw_output(self):
        if not self.win:
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
