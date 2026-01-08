import curses


class ScreenLayout:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.H, self.W = stdscr.getmaxyx()

        input_h = max(6, self.H * 2 // 5)
        table_h = self.H - input_h

        self.table_win = curses.newwin(table_h, self.W, 0, 0)
        bottom = curses.newwin(input_h, self.W, table_h, 0)

        left_w = self.W // 2
        right_w = self.W - left_w

        self.command_win = bottom.derwin(input_h, left_w, 0, 0)
        self.output_win = bottom.derwin(input_h, right_w, 0, left_w)