import curses


class ScreenLayout:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.H, self.W = stdscr.getmaxyx()

        input_h = max(6, self.H * 2 // 5)
        table_h = self.H - input_h

        # reserve one line at bottom for status bar
        status_h = 1
        self.table_win = curses.newwin(table_h, self.W, 0, 0)
        # grid pane must never own cursor
        self.table_win.leaveok(True)
        bottom = curses.newwin(input_h - status_h, self.W, table_h, 0)
        self.status_win = curses.newwin(status_h, self.W, table_h + input_h - status_h, 0)
        # do not let status bar steal cursor
        self.status_win.leaveok(True)

        left_w = self.W // 2
        right_w = self.W - left_w

        self.command_win = bottom.derwin(input_h - status_h, left_w, 0, 0)
        self.output_win = bottom.derwin(input_h - status_h, right_w, 0, left_w)
        # output pane must never own cursor
        self.output_win.leaveok(True)