# ~/Apps/vixl/orchestrator.py
import curses
import time
import os
import pandas as pd

from grid_pane import GridPane
from command_pane import CommandPane
from command_executor import CommandExecutor
from screen_layout import ScreenLayout
from config_paths import HISTORY_PATH, ensure_config_dirs
from file_type_handler import FileTypeHandler
from pagination import Paginator



class Orchestrator:
    def __init__(self, stdscr, app_state):
        self.stdscr = stdscr
        curses.curs_set(1)
        curses.raw()
        self.stdscr.nodelay(False)
        self.stdscr.timeout(100)

        ensure_config_dirs()

        self.state = app_state
        self.layout = ScreenLayout(stdscr)
        self.grid = GridPane(app_state.df)

        # ---- pagination ----
        self.paginator = Paginator(total_rows=len(self.state.df), page_size=1000)

        self.command = CommandPane()
        self.exec = CommandExecutor(app_state)

        self.focus = 0  # 0=df, 1=cmd, 2=overlay
        self.overlay_visible = False
        self.overlay_lines = []
        self.overlay_scroll = 0

        # ---- save-as prompt ----
        self.save_as_active = False
        self.save_as_buffer = ""
        self.save_as_cursor = 0
        self.save_as_hscroll = 0
        self.save_and_exit = False
        self.exit_requested = False

        # ---- DF cell editing state ----
        self.df_mode = 'normal'  # normal | cell_normal | cell_insert
        self.cell_buffer = ""
        self.cell_cursor = 0
        self.cell_hscroll = 0
        self.cell_col = None
        self.cell_leader_state = None  # None | 'leader' | 'c' | 'd'
        self.df_leader_state = None  # None | 'leader'

        # ---- status ----
        self.status_msg = None
        self.status_msg_until = 0

        # ---- history ----
        import os
        self.history_path = HISTORY_PATH
        self.history = []

        legacy_path = os.path.expanduser('~/.vixl_history')
        if os.path.exists(self.history_path):
            try:
                with open(self.history_path, 'r', encoding='utf-8') as f:
                    self.history = [l.rstrip('\n') for l in f if l.strip()][-100:]
            except Exception:
                self.history = []
        elif os.path.exists(legacy_path):
            try:
                with open(legacy_path, 'r', encoding='utf-8') as f:
                    data = [l.rstrip('\n') for l in f if l.strip()]
                self.history = data[-100:]
                with open(self.history_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(data) + ('\n' if data else ''))
            except Exception:
                self.history = []
        else:
            try:
                with open(self.history_path, 'w', encoding='utf-8') as f:
                    f.write('')
            except Exception:
                self.history = []

        # share history with command pane
        self.command.set_history(self.history)

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
                    # only allow row insertion while in df normal (hover) mode
                    if self.df_mode != 'normal':
                        return
                    row = self.state.build_default_row()
                    insert_at = self.grid.curr_row + 1 if len(self.state.df) > 0 else 0
                    new_row = pd.DataFrame([row], columns=self.state.df.columns)
                    self.state.df = pd.concat([
                        self.state.df.iloc[:insert_at],
                        new_row,
                        self.state.df.iloc[insert_at:],
                    ], ignore_index=True)
                    self.grid.df = self.state.df
                    self.paginator.update_total_rows(len(self.state.df))
                    self.paginator.ensure_row_visible(insert_at)
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
            r, c = self.grid.curr_row, self.grid.curr_col
            col = self.state.df.columns[c]
            val = self.state.df.iloc[r, c]
            base = '' if (val is None or pd.isna(val)) else str(val)

            if self.df_leader_state:
                state = self.df_leader_state
                self.df_leader_state = None
                if state == 'leader' and ch == ord('y'):
                    try:
                        import subprocess
                        tsv_data = self.state.df.to_csv(sep='\t', index=False)
                        subprocess.run(['wl-copy'], input=tsv_data, text=True, check=True)
                        self.status_msg = "DF copied"
                        self.status_msg_until = time.time() + 3
                    except Exception:
                        self.status_msg = "Copy failed"
                        self.status_msg_until = time.time() + 3
                    return

            if self.cell_leader_state:
                state = self.cell_leader_state
                self.cell_leader_state = None

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
                    # only allow row insertion while in df normal (hover) mode
                    if self.df_mode != 'normal':
                        return
                    row = self.state.build_default_row()
                    insert_at = self.grid.curr_row + 1 if len(self.state.df) > 0 else 0
                    new_row = pd.DataFrame([row], columns=self.state.df.columns)
                    self.state.df = pd.concat([
                        self.state.df.iloc[:insert_at],
                        new_row,
                        self.state.df.iloc[insert_at:],
                    ], ignore_index=True)
                    self.grid.df = self.state.df
                    self.paginator.update_total_rows(len(self.state.df))
                    self.paginator.ensure_row_visible(insert_at)
                    self.grid.curr_row = insert_at
                    self.grid.highlight_mode = 'cell'
                    return

            if ch == ord(','):
                self.df_leader_state = 'leader'
                self.cell_leader_state = None
                return

            if ch == ord('i'):
                self.cell_col = col
                self.cell_buffer = base
                if not self.cell_buffer.endswith(' '):
                    self.cell_buffer += ' '
                self.cell_cursor = len(self.cell_buffer) - 1
                self.df_mode = 'cell_insert'
                return

            if ch == ord('h'):
                self.grid.move_left()
            elif ch == ord('l'):
                self.grid.move_right()
            elif ch == ord('j'):
                if self.grid.curr_row + 1 >= self.paginator.page_end:
                    if self.paginator.page_end < self.paginator.total_rows:
                        self.paginator.next_page()
                        self.grid.row_offset = 0
                        self.grid.curr_row = self.paginator.page_start
                    else:
                        self.grid.curr_row = max(0, self.paginator.total_rows - 1)
                else:
                    self.grid.move_down()
            elif ch == ord('k'):
                if self.grid.curr_row - 1 < self.paginator.page_start:
                    if self.paginator.page_index > 0:
                        self.paginator.prev_page()
                        self.grid.row_offset = 0
                        self.grid.curr_row = max(self.paginator.page_start, self.paginator.page_end - 1)
                    else:
                        self.grid.curr_row = 0
                else:
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
                self.command.activate()
                self.focus = 1
            elif ch == ord('?'):
                self._show_shortcuts()
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
            if self.overlay_visible:
                curses.curs_set(0)
            elif self.save_as_active:
                curses.curs_set(1)
            else:
                curses.curs_set(1 if (self.focus == 1 and self.command.active) else 0)
        except curses.error:
            pass

        if not self.overlay_visible:
            self.grid.draw(
                self.layout.table_win,
                active=(self.focus == 0),
                editing=(self.focus == 0 and self.df_mode in ('cell_insert', 'cell_normal')),
                insert_mode=(self.focus == 0 and self.df_mode == 'cell_insert'),
                edit_row=self.grid.curr_row,
                edit_col=self.grid.curr_col,
                edit_buffer=self.cell_buffer,
                edit_cursor=self.cell_cursor,
                edit_hscroll=self.cell_hscroll,
                page_start=self.paginator.page_start,
                page_end=self.paginator.page_end,
            )

            sw = self.layout.status_win
            sw.erase()
            h, w = sw.getmaxyx()

            if self.save_as_active:
                prompt = "Save as: "
                text_w = max(1, w - len(prompt) - 1)
                if self.save_as_cursor < self.save_as_hscroll:
                    self.save_as_hscroll = self.save_as_cursor
                elif self.save_as_cursor > self.save_as_hscroll + text_w:
                    self.save_as_hscroll = self.save_as_cursor - text_w
                start = self.save_as_hscroll
                end = start + text_w
                visible = self.save_as_buffer[start:end]
                try:
                    sw.addnstr(0, 0, prompt, len(prompt))
                    sw.addnstr(0, len(prompt), visible, text_w)
                    sw.move(0, len(prompt) + (self.save_as_cursor - self.save_as_hscroll))
                except curses.error:
                    pass
                sw.refresh()
            else:
                cmd_active = (self.focus == 1 and self.command.active)

                if cmd_active:
                    self.command.draw(sw, active=True)
                    sw.refresh()
                else:
                    text = ""
                    now = time.time()
                    if self.status_msg and now < self.status_msg_until:
                        text = f" {self.status_msg}"
                    else:
                        if self.focus == 0:
                            if self.df_mode == 'cell_insert':
                                mode = 'DF:CELL-INSERT'
                            elif self.df_mode == 'cell_normal':
                                mode = 'DF:CELL-NORMAL'
                            else:
                                mode = 'DF'
                        elif self.focus == 1:
                            mode = 'CMD'
                        else:
                            mode = 'DF'
                        fname = os.path.basename(self.state.file_path) if self.state.file_path else ''
                        shape = f"{self.state.df.shape}"
                        page_total = self.paginator.page_count
                        page_info = f"Page {self.paginator.page_index + 1}/{page_total} rows {self.paginator.page_start}-{max(self.paginator.page_start, self.paginator.page_end - 1)} of {self.paginator.total_rows}"
                        text = f" {mode} | {fname} | {shape} | {page_info}"

                    try:
                        sw.addnstr(0, 0, text.ljust(w), w)
                    except curses.error:
                        pass
                    sw.refresh()


        if self.overlay_visible:
            self._draw_overlay()

    def _open_overlay(self, lines):
        max_h = min(self.layout.H // 2, self.layout.H - 2)
        content_h = len(lines) + 2  # box padding
        overlay_h = max(3, min(content_h, max_h))
        overlay_y = max(0, (self.layout.table_h - overlay_h) // 2)

        self.layout.overlay_h = overlay_h
        self.layout.overlay_win = curses.newwin(overlay_h, self.layout.W, overlay_y, 0)
        self.layout.overlay_win.leaveok(True)

        self.overlay_lines = lines
        self.overlay_scroll = 0
        self.overlay_visible = True
        self.focus = 2

    def _show_shortcuts(self):
        lines = [
            "Shortcuts",
            "",
            "Global",
            "  Ctrl+C / Ctrl+X - exit",
            "  Ctrl+S (df) - save",
            "  Ctrl+T (df) - save & exit",
            "  ? - show shortcuts",
            "",
            "Overlay (output)",
            "  Esc / q / Enter - close",
            "  j / k - scroll",
            "",
            "Command bar",
            "  : (from df) - enter",
            "  Enter / Ctrl+E - execute",
            "  Esc - cancel",
            "  Ctrl+P / Ctrl+N - history prev/next",
            "  Backspace, Left/Right, Home/End - edit/move",
            "",
            "DF normal",
            "  h / j / k / l - move",
            "  H / L - column highlight",
            "  J / K - row highlight",
            "  : - open command bar",
            "  i - edit cell (preload)",
            "  , e - edit cell (preload)",
            "  , c c - edit cell empty",
            "  , d c - clear cell",
            "  , n r - insert row below",
            "  , y - copy df to clipboard (TSV)",
            "  ? - shortcuts",
            "",
            "DF cell_insert",
            "  Type to edit; Backspace deletes; Esc commits to cell_normal",
            "",
            "DF cell_normal",
            "  h / l - move cursor within buffer",
            "  , e / , c c / , d c / , n r",
            "  i - insert; Esc - back to df normal",
        ]
        self._open_overlay(lines)

    def _draw_overlay(self):
        win = self.layout.overlay_win
        win.erase()
        h, w = win.getmaxyx()
        win.box()

        max_visible = max(0, h - 2)
        start = self.overlay_scroll
        end = start + max_visible
        for i, line in enumerate(self.overlay_lines[start:end]):
            try:
                win.addnstr(1 + i, 1, line, w - 2)
            except curses.error:
                pass

        # no helper footer; rely on memorized keys
        win.refresh()

    def _handle_overlay_key(self, ch):
        max_visible = max(0, self.layout.overlay_h - 2)
        max_scroll = max(0, len(self.overlay_lines) - max_visible)

        if ch in (27, ord('q'), 10, 13):
            self.overlay_visible = False
            self.focus = 0
            return
        if ch == ord('j'):
            self.overlay_scroll = min(max_scroll, self.overlay_scroll + 1)
        elif ch == ord('k'):
            self.overlay_scroll = max(0, self.overlay_scroll - 1)

    def _execute_command_buffer(self):
        code = self.command.get_buffer().strip()

        if not code:
            self.command.reset()
            self.focus = 0
            self.status_msg = "No command to execute"
            self.status_msg_until = time.time() + 3
            return

        lines = self.exec.execute(code)
        if lines:
            self._open_overlay(lines)
        else:
            self.overlay_visible = False
            self.overlay_lines = []
            self.focus = 0

        # clear command bar after execution
        self.command.reset()

        # sync grid with latest df and clamp cursor within bounds
        self.grid.df = self.state.df
        self.paginator.update_total_rows(len(self.state.df))
        self.grid.curr_row = min(self.grid.curr_row, max(0, len(self.grid.df) - 1))
        self.grid.curr_col = min(self.grid.curr_col, max(0, len(self.grid.df.columns) - 1))
        self.paginator.ensure_row_visible(self.grid.curr_row)

        if getattr(self.exec, '_last_success', False):
            self.history.append(code)
            self.history = self.history[-100:]
            self.command.set_history(self.history)
            try:
                with open(self.history_path, 'a', encoding='utf-8') as f:
                    f.write(code + '\n')
            except Exception:
                pass
            self.status_msg = "Command executed"
        else:
            self.status_msg = "Command failed"
        self.status_msg_until = time.time() + 3

    def _start_save_as(self, save_and_exit=False):
        self.save_as_active = True
        self.save_as_buffer = self.state.file_path or ''
        self.save_as_cursor = len(self.save_as_buffer)
        self.save_as_hscroll = 0
        self.save_and_exit = save_and_exit
        self.exit_requested = False
        self.overlay_visible = False
        self.focus = 0

    def _handle_save_as_key(self, ch):
        if not self.save_as_active:
            return

        if ch in (10, 13):  # Enter
            path = self.save_as_buffer.strip()
            if not path:
                self.status_msg = "Path required"
                self.status_msg_until = time.time() + 3
                return
            if not (path.lower().endswith('.csv') or path.lower().endswith('.parquet')):
                self.status_msg = "Save failed: use .csv or .parquet"
                self.status_msg_until = time.time() + 4
                return
            try:
                handler = FileTypeHandler(path)
                if hasattr(self.state, 'ensure_non_empty'):
                    self.state.ensure_non_empty()
                handler.save(self.state.df)
                self.state.file_handler = handler
                self.state.file_path = path
                self.status_msg = f"Saved {path}"
                self.status_msg_until = time.time() + 3
                self.save_as_active = False
                self.save_as_buffer = ""
                self.save_as_cursor = 0
                self.save_as_hscroll = 0
                if self.save_and_exit:
                    self.exit_requested = True
                self.save_and_exit = False
            except Exception as e:
                self.status_msg = f"Save failed: {e}"[: self.layout.W - 2]
                self.status_msg_until = time.time() + 4
            return

        if ch == 27:  # Esc
            self.save_as_active = False
            self.save_and_exit = False
            self.save_as_buffer = ""
            self.save_as_cursor = 0
            self.save_as_hscroll = 0
            self.status_msg = "Save canceled"
            self.status_msg_until = time.time() + 3
            return

        if ch in (curses.KEY_BACKSPACE, 127, 8):
            if self.save_as_cursor > 0:
                self.save_as_buffer = (
                    self.save_as_buffer[: self.save_as_cursor - 1]
                    + self.save_as_buffer[self.save_as_cursor :]
                )
                self.save_as_cursor -= 1
            return

        if ch == curses.KEY_LEFT:
            self.save_as_cursor = max(0, self.save_as_cursor - 1)
            return

        if ch == curses.KEY_RIGHT:
            self.save_as_cursor = min(len(self.save_as_buffer), self.save_as_cursor + 1)
            return

        if ch == curses.KEY_HOME:
            self.save_as_cursor = 0
            return

        if ch == curses.KEY_END:
            self.save_as_cursor = len(self.save_as_buffer)
            return

        if 32 <= ch <= 126:
            self.save_as_buffer = (
                self.save_as_buffer[: self.save_as_cursor]
                + chr(ch)
                + self.save_as_buffer[self.save_as_cursor :]
            )
            self.save_as_cursor += 1
            return

    def _save_df(self, save_and_exit=False):
        handler = getattr(self.state, 'file_handler', None)
        if handler is None:
            self._start_save_as(save_and_exit=save_and_exit)
            return False

        try:
            if hasattr(self.state, 'ensure_non_empty'):
                self.state.ensure_non_empty()
            handler.save(self.state.df)
            fname = self.state.file_path or ''
            self.status_msg = f"Saved {fname}" if fname else "Saved"
            self.status_msg_until = time.time() + 3
            if save_and_exit:
                self.exit_requested = True
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

            if ch in (3, 24):
                break

            if self.overlay_visible:
                self._handle_overlay_key(ch)
                self.redraw()
                continue

            if self.save_as_active:
                self._handle_save_as_key(ch)
                if self.exit_requested:
                    break
                self.redraw()
                continue

            if ch == -1:
                self.redraw()
                continue

            if ch in (3, 24):
                break

            if self.focus == 0 and ch in (19, 20):  # Ctrl+S / Ctrl+T
                saved = self._save_df(save_and_exit=(ch == 20))
                self.redraw()
                if self.exit_requested:
                    break
                if ch == 20 and saved:
                    break
                continue

            if self.focus == 0:
                self._handle_df_key(ch)
            elif self.focus == 1:
                result = self.command.handle_key(ch)
                if result == "submit":
                    self._execute_command_buffer()
                elif result == "cancel":
                    self.focus = 0

            self.redraw()
            if self.exit_requested:
                break

