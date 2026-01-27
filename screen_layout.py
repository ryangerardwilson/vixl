import curses


class ScreenLayout:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.H, self.W = stdscr.getmaxyx()

        # layout: table (main), shared bottom strip (status or command), optional overlay
        self.status_h = 1
        self.table_h = max(1, self.H - self.status_h)

        self.table_win = curses.newwin(self.table_h, self.W, 0, 0)
        # grid pane must never own cursor
        self.table_win.leaveok(True)

        # shared strip for status or command line
        self.status_win = curses.newwin(self.status_h, self.W, self.table_h, 0)
        # allow cursor to be positioned when command line is active
        self.status_win.leaveok(False)

        # overlay dimensions are computed dynamically when opened
        self.overlay_h = self.table_h
