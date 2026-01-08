class GridPane:
    def __init__(self, df):
        self.df = df
        self.scroll = 0

    def scroll_down(self):
        self.scroll = min(len(self.df) - 1, self.scroll + 1)

    def scroll_up(self):
        self.scroll = max(0, self.scroll - 1)

    def draw(self, win, active=False):
        win.erase()
        h, w = win.getmaxyx()
        headers = list(self.df.columns)
        rows = self.df.values.tolist()[self.scroll :]

        def fmt_row(row):
            return "".join(str(cell).ljust(12) for cell in row)

        try:
            win.addnstr(1, 1, fmt_row(headers), w - 2)
            win.addnstr(2, 1, "-" * (w - 2), w - 2)
            for i, row in enumerate(rows[: h - 4]):
                win.addnstr(i + 3, 1, fmt_row(row), w - 2)
        except Exception:
            pass

        if active:
            win.addnstr(h - 2, w - 8, " DF ", 6)
        win.box()
        win.refresh()