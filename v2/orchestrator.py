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
        self.state = app_state
        self.layout = ScreenLayout(stdscr)
        self.grid = GridPane(app_state.df)
        self.command = CommandPane()
        self.output = OutputPane()
        self.exec = CommandExecutor(app_state)
        self.focus = 1  # 0=grid,1=command,2=output

    def redraw(self):
        self.grid.draw(self.layout.table_win, active=self.focus == 0)
        self.output.draw(self.layout.output_win, active=self.focus == 2)
        self.command.draw(self.layout.command_win, active=self.focus == 1)

    def run(self):
        # match v2/temp behavior: clear + initial paint before input
        self.stdscr.clear()
        self.stdscr.refresh()
        self.redraw()  # initial render so UI appears immediately
        while True:
            ch = self.stdscr.getch()

            if ch == 23:  # Ctrl-W
                self.focus = (self.focus + 1) % 3
                self.redraw()
                continue

            if self.focus == 0:
                if ch == ord('j'):
                    self.grid.scroll_down()
                elif ch == ord('k'):
                    self.grid.scroll_up()

            elif self.focus == 2:
                if ch == ord('j'):
                    self.output.scroll_down()
                elif ch == ord('k'):
                    self.output.scroll_up()

            else:  # command pane
                if ch == 5:  # Ctrl-E execute
                    code = self.command.get_buffer().strip()
                    if code:
                        out = self.exec.execute(code)
                        self.output.set_lines(out)
                    self.redraw()
                    continue
                self.command.handle_key(ch)

            self.redraw()