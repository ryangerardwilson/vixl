import curses
import time
import subprocess
from grid_pane import GridPane
from command_pane import CommandPane
from output_pane import OutputPane
from command_executor import CommandExecutor
from screen_layout import ScreenLayout

LEADER_COMMANDS = {
    ',ya': 'ACTIVE',
    ',yap': 'ALL',
    ',yio': 'IO',
    ',o': 'OUT',
    ',df': 'DF',
}
LEADER_PREFIXES = {p[:i] for p in LEADER_COMMANDS for i in range(1, len(p) + 1)}
LEADER_TIMEOUT = 1.0


class Orchestrator:
    def __init__(self, stdscr, app_state):
        self.stdscr = stdscr
        curses.curs_set(1)
        curses.raw()
        self.stdscr.timeout(100)

        self.state = app_state
        self.layout = ScreenLayout(stdscr)
        self.grid = GridPane(app_state.df)
        self.command = CommandPane()
        self.output = OutputPane()
        self.exec = CommandExecutor(app_state)

        self.focus = 0  # 0=df,1=cmd,2=out
        self.command_history = []

        self.status_msg = None
        self.status_msg_until = 0

        # leader state
        self.leader_seq = None
        self.leader_start = 0.0

    def _execute_leader(self, seq: str):
        # pane switching leaders
        if seq == ',o':
            self.focus = 2
            return
        if seq == ',df':
            self.focus = 0
            return

        content = ""
        if seq == ',ya':
            if self.focus == 0:
                content = self.state.df.to_string()
            elif self.focus == 1:
                content = self.command.get_buffer()
            else:
                content = "\n".join(self.output.lines)
        elif seq == ',yap':
            content = (
                self.state.df.to_string()
                + "\n\n"
                + self.command.get_buffer()
                + "\n\n"
                + "\n".join(self.output.lines)
            )
        elif seq == ',yio':
            last = self.command_history[-1] if self.command_history else ""
            content = last + "\n\n" + "\n".join(self.output.lines)

        if content:
            try:
                subprocess.run(['wl-copy'], input=content, text=True)
                self.status_msg = f"{seq} → copied"
                self.status_msg_until = time.time() + 5.0
            except Exception:
                self.status_msg = None
                self.status_msg_until = 0

    def redraw(self):
        try:
            curses.curs_set(1 if self.focus == 1 else 0)
        except curses.error:
            pass

        self.grid.draw(self.layout.table_win, active=self.focus == 0)
        self.output.draw(self.layout.output_win, active=False)

        sw = self.layout.status_win
        sw.erase()
        h, w = sw.getmaxyx()

        try:
            mem_bytes = int(self.state.df.memory_usage(deep=True).sum())
            mem = f"{mem_bytes/1024/1024:.1f}MB"
        except Exception:
            mem = "?MB"

        now = time.time()
        if self.status_msg and now < self.status_msg_until:
            text = f" {self.status_msg}"
        else:
            if self.status_msg and now >= self.status_msg_until:
                self.status_msg = None
                self.status_msg_until = 0
            if self.leader_seq:
                text = f" {self.leader_seq}"
            else:
                if self.focus == 0:
                    mode = "DF"
                elif self.focus == 1:
                    mode = f"CMD:{self.command.mode.upper()}"
                else:
                    mode = "OUT"
                fname = self.state.file_path or ""
                shape = f"{self.state.df.shape}"
                text = f" {mode} | {fname} | {shape} | {mem}"

        try:
            sw.addnstr(0, 0, text.ljust(w), w)
        except curses.error:
            pass
        sw.refresh()

        self.command.draw(self.layout.command_win, active=self.focus == 1)

    def _leader_tick(self, now: float):
        # timeout handling
        if self.leader_seq and now - self.leader_start >= LEADER_TIMEOUT:
            if self.leader_seq in LEADER_COMMANDS:
                self._execute_leader(self.leader_seq)
            # clear leader state regardless (complete or incomplete)
            self.leader_seq = None

    def run(self):
        self.stdscr.clear()
        self.stdscr.refresh()
        self.redraw()

        while True:
            ch = self.stdscr.getch()
            now = time.time()

            if ch == -1:
                self._leader_tick(now)
                self.redraw()
                continue

            # global
            if ch == 24:  # Ctrl-X
                break
            if ch == 19:  # Ctrl-S
                try:
                    self.state.save()
                except Exception:
                    pass
                self.status_msg = "Saved"
                self.status_msg_until = time.time() + 5.0
                self.redraw()
                continue
            if ch == 20:  # Ctrl-T
                try:
                    self.state.save()
                except Exception:
                    pass
                return

            if ch == 23:  # Ctrl-W
                # cancel any in-progress leader to avoid UI glitch
                self.leader_seq = None
                if self.status_msg_until == float('inf'):
                    self.status_msg = None
                    self.status_msg_until = 0
                self.focus = (self.focus + 1) % 3
                self.redraw()
                continue

            # leader handling
            if self.leader_seq is not None:
                if 0 <= ch <= 0x10FFFF:
                    # extend leader sequence
                    self.leader_seq += chr(ch)
                    self.leader_start = now  # reset timeout on each valid key

                    # invalid prefix -> cancel immediately
                    if self.leader_seq not in LEADER_PREFIXES:
                        self.leader_seq = None

                    # complete and not a prefix of any longer command -> execute now
                    elif (self.leader_seq in LEADER_COMMANDS and
                          not any(p != self.leader_seq and p.startswith(self.leader_seq)
                                  for p in LEADER_COMMANDS)):
                        self._execute_leader(self.leader_seq)
                        self.leader_seq = None
                self.redraw()
                continue

            if ch == ord(','):
                self.leader_seq = ','
                self.leader_start = now
                self.redraw()
                continue

            # pane-specific
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
                elif ch == ord(':'):
                    # plain command entry, preserve existing buffer
                    self.focus = 1
                elif ch == ord('i'):
                    # insert with context-aware prefill
                    r = self.grid.curr_row
                    c = self.grid.curr_col
                    col = self.state.df.columns[c]
                    df = self.state.df
                    if self.grid.highlight_mode == 'cell':
                        cmd = f"df.loc[{r}, '{col}'] = {repr(df.iloc[r, c])}"
                    elif self.grid.highlight_mode == 'row':
                        cmd = f"df.loc[{r}] = {repr(df.iloc[r].to_dict())}"
                    else:
                        # column-level insert defaults to rename intent
                        cmd = f"df = df.rename(columns={{'{col}': '{col}'}})"
                    self.command.set_buffer(cmd)
                    self.focus = 1

            elif self.focus == 2:
                if ch == ord('j'):
                    self.output.scroll_down()
                elif ch == ord('k'):
                    self.output.scroll_up()

            else:
                # command pane
                if ch == 27 and self.command.mode == 'normal':  # ESC from normal -> back to DF
                    self.focus = 0
                elif ch == 5:  # Ctrl-E execute
                    code = self.command.get_buffer().strip()
                    if code:
                        self.command_history.append(code)
                        out = self.exec.execute(code)
                        self.output.set_lines(out)
                        # ensure grid reflects latest df
                        self.grid.df = self.state.df
                    self.command.reset()
                    self.focus = 0
                else:
                    self.command.handle_key(ch)

            self.redraw()