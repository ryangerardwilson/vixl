import curses
from grid_pane import GridPane
from command_pane import CommandPane
from output_pane import OutputPane
from command_executor import CommandExecutor
from screen_layout import ScreenLayout


class Orchestrator:
    def __init__(self, stdscr, app_state):
        self.stdscr = stdscr
        curses.curs_set(1)
        curses.raw()  # disable terminal flow control (Ctrl-S / Ctrl-Q)
        self.state = app_state
        self.layout = ScreenLayout(stdscr)
        self.grid = GridPane(app_state.df)
        self.command = CommandPane()
        self.output = OutputPane()
        self.exec = CommandExecutor(app_state)
        self.focus = 0  # 0=grid,1=command,2=output
        self.command_history = []
        self.history_idx = None

    def redraw(self):
        # cursor ownership: only command pane shows cursor
        try:
            curses.curs_set(1 if self.focus == 1 else 0)
        except curses.error:
            pass

        self.grid.draw(self.layout.table_win, active=self.focus == 0)
        self.output.draw(self.layout.output_win, active=False)

        # status bar (must not steal cursor)
        sw = self.layout.status_win
        sw.erase()
        h, w = sw.getmaxyx()
        if self.focus == 0:
            mode = "DF"
        elif self.focus == 1:
            mode = f"CMD:{self.command.mode.upper()}"
        else:
            mode = "OUT"
        shape = f"{self.state.df.shape}"
        fname = self.state.file_path or ""
        text = f" {mode} | {fname} | {shape}"
        try:
            sw.addnstr(0, 0, text.ljust(w), w, curses.A_REVERSE)
        except curses.error:
            pass
        sw.refresh()

        # draw command pane LAST so it owns the cursor
        self.command.draw(self.layout.command_win, active=self.focus == 1)

    def run(self):
        # match v2/temp behavior: clear + initial paint before input
        self.stdscr.clear()
        self.stdscr.refresh()
        self.redraw()  # initial render so UI appears immediately
        while True:
            ch = self.stdscr.getch()

            # global shortcuts
            if ch == 24:  # Ctrl-X -> exit without saving
                break
            if ch == 19:  # Ctrl-S -> save
                try:
                    self.state.save()
                except Exception:
                    pass
                self.redraw()
                continue
            if ch == 20:  # Ctrl-T -> save and exit
                try:
                    self.state.save()
                except Exception:
                    pass
                return

            if ch == 23:  # Ctrl-W
                # cycle focus: grid -> command -> output
                self.focus = (self.focus + 1) % 3
                self.redraw()
                continue

            if self.focus == 0:
                if ch == ord('h'):
                    self.grid.move_left()
                elif ch == ord('l'):
                    self.grid.move_right()
                elif ch == ord('j'):
                    self.grid.move_down()
                elif ch == ord('k'):
                    self.grid.move_up()
                elif ch == ord('J'):
                    self.grid.move_row_down()
                elif ch == ord('K'):
                    self.grid.move_row_up()
                elif ch == ord('H'):
                    self.grid.move_col_left()
                elif ch == ord('L'):
                    self.grid.move_col_right()
                elif ch == ord('i'):
                    r = self.grid.curr_row
                    c = self.grid.curr_col
                    col_name = self.state.df.columns[c]
                    df = self.state.df

                    if self.grid.highlight_mode == 'cell':
                        val = df.iloc[r, c]
                        cmd = f"df.loc[{r}, '{col_name}'] = {repr(val)}"
                    elif self.grid.highlight_mode == 'row':
                        row_dict = df.iloc[r].to_dict()
                        cmd = f"df.loc[{r}] = {repr(row_dict)}"
                    elif self.grid.highlight_mode == 'column':
                        series = df[col_name]
                        cmd = f"df['{col_name}'] = {repr(series.tolist())}"
                    else:
                        cmd = ""

                    self.command.set_buffer(cmd)
                    self.focus = 1

            elif self.focus == 2:
                if ch == ord('j'):
                    self.output.scroll_down()
                elif ch == ord('k'):
                    self.output.scroll_up()

            else:  # command pane
                if ch == 5:  # Ctrl-E execute
                    code = self.command.get_buffer().strip()
                    if code:
                        self.command_history.append(code)
                        self.history_idx = None
                        out = self.exec.execute(code)
                        self.output.set_lines(out)
                    self.command.reset()  # clear + normal mode
                    self.focus = 0  # return focus to grid
                    self.redraw()
                    continue

                # Ctrl-P / Ctrl-N for history
                if ch == 16:  # Ctrl-P
                    if self.command_history:
                        if self.history_idx is None:
                            self.history_idx = len(self.command_history) - 1
                        else:
                            self.history_idx = max(0, self.history_idx - 1)
                        self.command.set_buffer(self.command_history[self.history_idx])
                    self.redraw()
                    continue

                if ch == 14:  # Ctrl-N
                    if self.command_history and self.history_idx is not None:
                        if self.history_idx < len(self.command_history) - 1:
                            self.history_idx += 1
                            self.command.set_buffer(self.command_history[self.history_idx])
                        else:
                            self.history_idx = None
                            self.command.reset()
                    self.redraw()
                    continue

                self.command.handle_key(ch)

            self.redraw()