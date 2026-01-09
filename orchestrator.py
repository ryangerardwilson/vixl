import curses
import time
import subprocess
import pandas as pd

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

        self.focus = 0  # 0=df, 1=cmd, 2=out
        self.io_visible = False

        # ---- DF cell editing state ----
        self.df_mode = 'normal'  # normal | cell_insert | cell_normal
        self.last_nav = None     # hjkl | HJKL | other
        self.cell_buffer = ""
        self.cell_cursor = 0
        self.cell_col = None
        # explicit cell command model (no dummy space)
        self.has_sentinel_space = False
        # cell-local leader state: None | 'leader' | 'c' | 'd'
        self.cell_leader_state = None

        # ---- status / leader ----
        self.status_msg = None
        self.status_msg_until = 0
        self.leader_seq = None
        self.leader_start = 0.0

        # ---- history ----
        import os
        self.history_idx = None
        self.history_path = os.path.expanduser('~/.vixl_history')
        self.history = []
        if os.path.exists(self.history_path):
            try:
                with open(self.history_path, 'r', encoding='utf-8') as f:
                    self.history = [l.rstrip('\n') for l in f if l.strip()][-100:]
            except Exception:
                self.history = []

    # ---------------- helpers ----------------

    def _coerce_cell_value(self, col, text):
        dtype = self.state.df[col].dtype
        if pd.api.types.is_integer_dtype(dtype):
            return int(text)
        if pd.api.types.is_float_dtype(dtype):
            return float(text)
        if pd.api.types.is_bool_dtype(dtype):
            return text.lower() in ('1', 'true', 'yes')
        return text

    def _execute_leader(self, seq):
        if seq == ',o':
            self.focus = 2
            return
        if seq == ',df':
            self.focus = 0
            return

        content = ''
        if seq == ',ya':
            if self.focus == 0:
                content = self.state.df.to_string()
            elif self.focus == 1:
                content = self.command.get_buffer()
            else:
                content = '\n'.join(self.output.lines)
        elif seq == ',yap':
            content = (
                self.state.df.to_string() + '\n\n'
                + self.command.get_buffer() + '\n\n'
                + '\n'.join(self.output.lines)
            )
        elif seq == ',yio':
            last = self.history[-1] if self.history else ''
            content = last + '\n\n' + '\n'.join(self.output.lines)

        if content:
            try:
                subprocess.run(['wl-copy'], input=content, text=True)
                self.status_msg = f"{seq} → copied"
                self.status_msg_until = time.time() + 5
            except Exception:
                pass

    # ---------------- DF handling ----------------

    def _handle_df_key(self, ch):
        # ----- cell insert -----
        if self.df_mode == 'cell_insert':
            # Esc -> cell normal (no dummy space model)
            if ch == 27:
                # exit insert: trim spaces, move cursor left (vim semantics)
                self.cell_buffer = self.cell_buffer.strip()
                self.cell_cursor = min(self.cell_cursor, len(self.cell_buffer))
                self.cell_cursor = max(0, self.cell_cursor - 1)
                self.df_mode = 'cell_normal'
                return

            # Backspace handling (KEY_BACKSPACE, DEL, Ctrl-H)
            if ch in (curses.KEY_BACKSPACE, 127, 8):
                if self.cell_cursor > 0:
                    self.cell_buffer = (
                        self.cell_buffer[:self.cell_cursor - 1]
                        + self.cell_buffer[self.cell_cursor:]
                    )
                    self.cell_cursor -= 1
                return

            # Printable character insertion
            if 0 <= ch <= 0x10FFFF:
                try:
                    ch_str = chr(ch)
                except ValueError:
                    return
                self.cell_buffer = (
                    self.cell_buffer[:self.cell_cursor]
                    + ch_str
                    + self.cell_buffer[self.cell_cursor:]
                )
                self.cell_cursor += 1
            return

        # ----- cell normal -----
        if self.df_mode == 'cell_normal':
            s = self.cell_buffer
            buf_len = len(s)

            # cell-local leader handling (explicit commands)
            if self.cell_leader_state:
                state = self.cell_leader_state
                self.cell_leader_state = None

                if state == 'leader':
                    if ch == ord('e'):
                        # ,e → append with sentinel space for stable cursor
                        if not self.cell_buffer.endswith(' '):
                            self.cell_buffer += ' '
                        self.cell_cursor = len(self.cell_buffer) - 1
                        self.df_mode = 'cell_insert'
                        return
                    if ch == ord('c'):
                        self.cell_leader_state = 'c'
                        return
                    if ch == ord('d'):
                        self.cell_leader_state = 'd'
                        return
                    return

                if state == 'c' and ch == ord('c'):
                    # ,cc → change cell
                    self.cell_buffer = ""
                    self.cell_cursor = 0
                    self.df_mode = 'cell_insert'
                    return

                if state == 'd' and ch == ord('c'):
                    # ,dc → delete cell
                    self.cell_buffer = ""
                    self.cell_cursor = 0
                    return

                return

            if ch == ord(','):
                self.cell_leader_state = 'leader'
                return

            if ch == ord('h'):
                # move left (insertion index)
                self.cell_cursor = max(0, self.cell_cursor - 1)
            elif ch == ord('l'):
                # move right (insertion index)
                self.cell_cursor = min(len(self.cell_buffer), self.cell_cursor + 1)
            elif ch == ord('w'):
                i = self.cell_cursor
                while i < len(s) and not s[i].isspace():
                    i += 1
                while i < len(s) and s[i].isspace():
                    i += 1
                self.cell_cursor = i
            elif ch == ord('b'):
                i = max(0, self.cell_cursor - 1)
                while i > 0 and s[i].isspace():
                    i -= 1
                while i > 0 and not s[i-1].isspace():
                    i -= 1
                self.cell_cursor = i
            elif ch == ord('i'):
                # enter insert mode like vim 'i': insert before character under cursor
                # normal-mode cursor is on char at (cell_cursor - 1)
                self.cell_cursor = max(0, self.cell_cursor - 1)
                self.df_mode = 'cell_insert'
                return
            elif ch == 27:
                r, c = self.grid.curr_row, self.grid.curr_col
                col = self.cell_col
                try:
                    commit_val = s
                    if self.has_sentinel_space and commit_val.endswith(' '):
                        commit_val = commit_val[:-1]
                    val = self._coerce_cell_value(col, commit_val)
                    self.state.df.iloc[r, c] = val
                except Exception:
                    self.status_msg = f"Invalid value for column '{col}'"
                    self.status_msg_until = time.time() + 3
                self.df_mode = 'normal'
                self.cell_buffer = ""
                self.has_sentinel_space = False
            return

        # ----- normal df -----
        # cell commands from hover (explicit only)
        if self.df_mode == 'normal':
            # cell-command leader handling in hover mode
            if self.cell_leader_state:
                state = self.cell_leader_state
                self.cell_leader_state = None
                r, c = self.grid.curr_row, self.grid.curr_col
                col = self.state.df.columns[c]
                val = self.state.df.iloc[r, c]
                base = '' if val is None else str(val)

                if state == 'leader':
                    if ch == ord('e'):
                        # ,e from hover → append with sentinel space
                        self.cell_col = col
                        self.cell_buffer = base
                        if not self.cell_buffer.endswith(' '):
                            self.cell_buffer += ' '
                        self.cell_cursor = len(self.cell_buffer) - 1
                        self.df_mode = 'cell_insert'
                        return
                    if ch == ord('c'):
                        self.cell_leader_state = 'c'
                        return
                    if ch == ord('d'):
                        self.cell_leader_state = 'd'
                        return
                    return

                if state == 'c' and ch == ord('c'):
                    # ,cc from hover → change
                    self.cell_col = col
                    self.cell_buffer = ''
                    self.cell_cursor = 0
                    self.df_mode = 'cell_insert'
                    return

                if state == 'd' and ch == ord('c'):
                    # ,dc from hover → delete immediately
                    try:
                        self.state.df.iloc[r, c] = self._coerce_cell_value(col, '')
                    except Exception:
                        self.state.df.iloc[r, c] = ''
                    return

            if ch == ord(','):
                self.cell_leader_state = 'leader'
                return

        if ch in (ord('h'), ord('j'), ord('k'), ord('l')):
            self.last_nav = 'hjkl'
        elif ch in (ord('H'), ord('J'), ord('K'), ord('L')):
            self.last_nav = 'HJKL'
        else:
            self.last_nav = 'other'

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
            self.io_visible = True
            self.focus = 1
        elif ch == ord('i'):
            if self.last_nav == 'HJKL':
                r, c = self.grid.curr_row, self.grid.curr_col
                col = self.state.df.columns[c]
                df = self.state.df
                if self.grid.highlight_mode == 'cell':
                    cmd = f"df.loc[{r}, '{col}'] = {repr(df.iloc[r, c])}"
                elif self.grid.highlight_mode == 'row':
                    cmd = f"df.loc[{r}] = {repr(df.iloc[r].to_dict())}"
                else:
                    cmd = f"df = df.rename(columns={{'{col}': '{col}'}})"
                self.command.set_buffer(cmd)
                self.io_visible = True
                self.focus = 1
            else:
                r, c = self.grid.curr_row, self.grid.curr_col
                self.cell_col = self.state.df.columns[c]
                val = self.state.df.iloc[r, c]
                base = '' if val is None else str(val)
                # add sentinel space for insert mode
                self.cell_buffer = base + ' '
                self.cell_cursor = len(base)
                self.has_sentinel_space = True
                self.df_mode = 'cell_insert'

    # ---------------- UI ----------------

    def redraw(self):
        try:
            curses.curs_set(1 if self.focus == 1 else 0)
        except curses.error:
            pass

        self.grid.draw(
            self.layout.table_win,
            active=self.focus == 0,
            editing=(self.focus == 0 and self.df_mode in ('cell_insert', 'cell_normal')),
            insert_mode=(self.focus == 0 and self.df_mode == 'cell_insert'),
            edit_row=self.grid.curr_row,
            edit_col=self.grid.curr_col,
            edit_buffer=self.cell_buffer,
            edit_cursor=self.cell_cursor,
        )

        if self.io_visible:
            self.output.draw(self.layout.output_win, active=False)
        else:
            self.layout.output_win.erase()
            self.layout.output_win.refresh()

        sw = self.layout.status_win
        sw.erase()
        h, w = sw.getmaxyx()

        now = time.time()
        if self.status_msg and now < self.status_msg_until:
            text = f" {self.status_msg}"
        else:
            if self.leader_seq:
                text = f" {self.leader_seq}"
            else:
                if self.focus == 0:
                    if self.df_mode == 'cell_insert':
                        mode = 'DF:CELL-INSERT'
                    elif self.df_mode == 'cell_normal':
                        mode = 'DF:CELL-NORMAL'
                    else:
                        mode = 'DF'
                elif self.focus == 1:
                    mode = f"CMD:{self.command.mode.upper()}"
                else:
                    mode = 'OUT'
                fname = self.state.file_path or ''
                shape = f"{self.state.df.shape}"
                text = f" {mode} | {fname} | {shape}"

        try:
            sw.addnstr(0, 0, text.ljust(w), w)
        except curses.error:
            pass
        sw.refresh()

        if self.io_visible:
            self.command.draw(self.layout.command_win, active=self.focus == 1)
        else:
            self.layout.command_win.erase()
            self.layout.command_win.refresh()

    # ---------------- main loop ----------------

    def run(self):
        self.stdscr.clear()
        self.stdscr.refresh()
        self.redraw()

        while True:
            ch = self.stdscr.getch()
            now = time.time()

            # global leader disabled when DF pane may handle cell commands
            leader_enabled = not (
                (self.focus == 1 and self.command.mode == 'insert') or
                (self.focus == 0)
            )

            if ch == -1:
                if leader_enabled and self.leader_seq and now - self.leader_start >= LEADER_TIMEOUT:
                    if self.leader_seq in LEADER_COMMANDS:
                        self._execute_leader(self.leader_seq)
                    self.leader_seq = None
                self.redraw()
                continue

            if ch == 24:
                break

            if leader_enabled and self.leader_seq is not None:
                self.leader_seq += chr(ch)
                self.leader_start = now
                if self.leader_seq not in LEADER_PREFIXES:
                    self.leader_seq = None
                elif self.leader_seq in LEADER_COMMANDS:
                    self._execute_leader(self.leader_seq)
                    self.leader_seq = None
                self.redraw()
                continue

            if ch == ord(','):
                # DF pane gets first chance to consume ',' for cell commands
                if self.focus == 0:
                    self._handle_df_key(ch)
                    self.redraw()
                    continue
                if leader_enabled:
                    self.leader_seq = ','
                    self.leader_start = now
                    self.redraw()
                    continue

            if self.focus == 0:
                self._handle_df_key(ch)
            elif self.focus == 2:
                if ch == 27:
                    self.focus = 1
                    self.io_visible = True
                elif ch == ord('j'):
                    self.output.scroll_down()
                elif ch == ord('k'):
                    self.output.scroll_up()
            else:
                if ch == 27 and self.command.mode == 'normal':
                    self.focus = 0
                    self.io_visible = False
                else:
                    self.command.handle_key(ch)

            self.redraw()
