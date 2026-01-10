import curses


class ScreenLayout:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.H, self.W = stdscr.getmaxyx()

        # layout: table (main), status bar (1 line), command bar (1 line), optional overlay
        self.status_h = 1
        self.cmd_h = 1

        self.table_h = max(1, self.H - self.status_h - self.cmd_h)

        self.table_win = curses.newwin(self.table_h, self.W, 0, 0)
        # grid pane must never own cursor
        self.table_win.leaveok(True)

        self.status_win = curses.newwin(self.status_h, self.W, self.table_h, 0)
        # do not let status bar steal cursor
        self.status_win.leaveok(True)

        self.cmd_win = curses.newwin(self.cmd_h, self.W, self.table_h + self.status_h, 0)

        # overlay is a centered modal window over the table region
        self.overlay_h = max(3, min(10, self.H - 2))
        overlay_y = max(0, (self.table_h - self.overlay_h) // 2)
        self.overlay_win = curses.newwin(self.overlay_h, self.W, overlay_y, 0)
        # overlay should never own cursor
        self.overlay_win.leaveok(True)
