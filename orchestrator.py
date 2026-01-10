# ~/Apps/vixl/orchestrator.py
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
        self.df_mode = 'normal'  # normal | cell_normal | cell_insert
        self.cell_buffer = ""
        self.cell_cursor = 0
        self.cell_hscroll = 0
        self.cell_col = None
        self.cell_leader_state = None  # None | 'leader' | 'c' | 'd'

        # ---- status / leader ----
        self.status_msg = None
        self.status_msg_until = 0
        self.leader_seq = None
        self.leader_start = 0.0

        # ---- history ----
        import os
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
            return int(text) if text != '' else None
        if pd.api.types.is_float_dtype(dtype):
            return float(text) if text != '' else None
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
        # ---------- cell insert ----------
        if self.df_mode == 'cell_insert':
            if ch == 27:  # Esc
                self.cell_buffer = self.cell_buffer.strip()

                r, c = self.grid.curr_row, self.grid.curr_col
                col = self.cell_col
                try:
                    val = self._coerce_cell_value(col, self.cell_buffer)
                    self.state.df.iloc[r, c] = val
                except Exception:
                    self.status_msg = f"Invalid value for column '{col}'"
                    self.status_msg_until = time.time() + 3

                # Clean reset for normal mode
                self.cell_cursor = 0
                self.cell_hscroll = 0
                self.df_mode = 'cell_normal'

                return

            if ch in (curses.KEY_BACKSPACE, 127, 8):
                if self.cell_cursor > 0:
                    self.cell_buffer = (
                        self.cell_buffer[:self.cell_cursor - 1]
                        + self.cell_buffer[self.cell_cursor:]
                    )
                    self.cell_cursor -= 1
                self._autoscroll_insert()
                return

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
                self._autoscroll_insert()
            return

        # ---------- cell normal ----------
        if self.df_mode == 'cell_normal':
            if self.cell_leader_state:
                state = self.cell_leader_state
                self.cell_leader_state = None

                if state == 'leader':
                    if ch == ord('e'):
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
                    if ch == ord('n'):
                        self.cell_leader_state = 'n'
                        return
                    return

                if state == 'c' and ch == ord('c'):
                    self.cell_buffer = ''
                    self.cell_cursor = 0
                    self.cell_hscroll = 0
                    self.df_mode = 'cell_insert'
                    return

                if state == 'd' and ch == ord('c'):
                    self.cell_buffer = ''
                    self.cell_cursor = 0
                    self.cell_hscroll = 0
                    return

                if state == 'n' and ch == ord('r'):
                    row = self.state.build_default_row()
                    insert_at = self.grid.curr_row + 1 if len(self.state.df) > 0 else 0
                    new_row = pd.DataFrame([row], columns=self.state.df.columns)
                    self.state.df = pd.concat([
                        self.state.df.iloc[:insert_at],
                        new_row,
                        self.state.df.iloc[insert_at:],
                    ], ignore_index=True)
                    self.grid.df = self.state.df
                    self.grid.curr_row = insert_at
                    self.grid.highlight_mode = 'cell'
                    return

            if ch == ord(','):
                self.cell_leader_state = 'leader'
                return

            buf_len = len(self.cell_buffer)
            cw = self.grid.get_col_width(self.grid.curr_col)

            moved = False
            if ch == ord('h'):
                if self.cell_cursor > 0:
                    self.cell_cursor -= 1
                    moved = True
            elif ch == ord('l'):
                if self.cell_cursor < buf_len:
                    self.cell_cursor += 1
                    moved = True

            if moved:
                # FINAL PERFECT SCROLLING - Vim-like on right edge
                if self.cell_cursor < self.cell_hscroll:
                    self.cell_hscroll = self.cell_cursor
                elif self.cell_cursor >= self.cell_hscroll + cw:  # >= allows cursor on last char perfectly
                    self.cell_hscroll = self.cell_cursor - cw + 1

                max_scroll = max(0, buf_len - cw + 1) if buf_len >= cw else 0
                self.cell_hscroll = max(0, min(self.cell_hscroll, max_scroll))
                return

            if ch == ord('i'):
                self.df_mode = 'cell_insert'
                return

            if ch == 27:  # Esc - exit cell editing
                self.df_mode = 'normal'
                self.cell_buffer = ''
                self.cell_hscroll = 0
                return

            return

        # ---------- df normal (hover) ----------
        if self.df_mode == 'normal':
            if self.cell_leader_state:
                state = self.cell_leader_state
                self.cell_leader_state = None
                r, c = self.grid.curr_row, self.grid.curr_col
                col = self.state.df.columns[c]
                val = self.state.df.iloc[r, c]
                base = '' if val is None else str(val)

                if state == 'leader':
                    if ch == ord('e'):
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
                    if ch == ord('n'):
                        self.cell_leader_state = 'n'
                        return
                    return

                if state == 'c' and ch == ord('c'):
                    self.cell_col = col
                    self.cell_buffer = ''
                    self.cell_cursor = 0
                    self.cell_hscroll = 0
                    self.df_mode = 'cell_insert'
                    return

                if state == 'd' and ch == ord('c'):
                    try:
                        self.state.df.iloc[r, c] = self._coerce_cell_value(col, '')
                    except Exception:
                        self.state.df.iloc[r, c] = ''
                    return

                if state == 'n' and ch == ord('r'):
                    row = self.state.build_default_row()
                    insert_at = self.grid.curr_row + 1 if len(self.state.df) > 0 else 0
                    new_row = pd.DataFrame([row], columns=self.state.df.columns)
                    self.state.df = pd.concat([
                        self.state.df.iloc[:insert_at],
                        new_row,
                        self.state.df.iloc[insert_at:],
                    ], ignore_index=True)
                    self.grid.df = self.state.df
                    self.grid.curr_row = insert_at
                    self.grid.highlight_mode = 'cell'
                    return

            if ch == ord(','):
                self.cell_leader_state = 'leader'
                return

            if ch == ord('i'):
                self.status_msg = "Use ,e or ,cc to edit cell"
                self.status_msg_until = time.time() + 2
                return

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
            return

    def _autoscroll_insert(self):
        cw = self.grid.get_col_width(self.grid.curr_col)
        if self.cell_cursor < self.cell_hscroll:
            self.cell_hscroll = self.cell_cursor
        elif self.cell_cursor > self.cell_hscroll + cw - 1:
            self.cell_hscroll = self.cell_cursor - (cw - 1)

        max_scroll = max(0, len(self.cell_buffer) - cw + 1) if len(self.cell_buffer) >= cw else 0
        self.cell_hscroll = max(0, min(self.cell_hscroll, max_scroll))

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
            edit_hscroll=self.cell_hscroll,
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

        # ---------------- helpers ----------------

    def _save_df(self):
        handler = getattr(self.state, 'file_handler', None)
        if handler is None:
            self.status_msg = "No file handler available"
            self.status_msg_until = time.time() + 4
            return False

        try:
            if hasattr(self.state, 'ensure_non_empty'):
                self.state.ensure_non_empty()
            handler.save(self.state.df)
            fname = self.state.file_path or ''
            self.status_msg = f"Saved {fname}" if fname else "Saved"
            self.status_msg_until = time.time() + 3
            return True
        except Exception as e:
            self.status_msg = f"Save failed: {e}"[: self.layout.W - 2]
            self.status_msg_until = time.time() + 4
            return False

    # ---------------- main loop ----------------

    def run(self):
        self.stdscr.clear()
        self.stdscr.refresh()
        self.redraw()

        while True:
            ch = self.stdscr.getch()
            now = time.time()

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

            if ch in (3, 24):
                break

            if self.focus == 0 and ch in (19, 20):  # Ctrl+S / Ctrl+T
                saved = self._save_df()
                self.redraw()
                if ch == 20 and saved:
                    break
                continue

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

            if ch == ord(',') and leader_enabled:
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

