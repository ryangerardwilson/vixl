# ~/Apps/vixl/orchestrator.py
import curses
import time
import os

from grid_pane import GridPane
from command_pane import CommandPane
from command_executor import CommandExecutor
from screen_layout import ScreenLayout
from config_paths import HISTORY_PATH, ensure_config_dirs
from file_type_handler import FileTypeHandler
from pagination import Paginator
from history_manager import HistoryManager
from df_editor import DfEditor


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

        # ---- status ----
        self.status_msg = None
        self.status_msg_until = 0

        # ---- history ----
        legacy_path = os.path.expanduser('~/.vixl_history')
        self.history_mgr = HistoryManager(HISTORY_PATH, legacy_path=legacy_path, max_items=100)
        self.history = self.history_mgr.load()

        # share history with command pane
        self.command.set_history(self.history)

        # ---- DF editor ----
        self.df_editor = DfEditor(self.state, self.grid, self.paginator, self._set_status)

    # ---------------- helpers ----------------

    def _set_status(self, msg, seconds=3):
        self.status_msg = msg
        self.status_msg_until = time.time() + seconds

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
                editing=(self.focus == 0 and self.df_editor.mode in ('cell_insert', 'cell_normal')),
                insert_mode=(self.focus == 0 and self.df_editor.mode == 'cell_insert'),
                edit_row=self.grid.curr_row,
                edit_col=self.grid.curr_col,
                edit_buffer=self.df_editor.cell_buffer,
                edit_cursor=self.df_editor.cell_cursor,
                edit_hscroll=self.df_editor.cell_hscroll,
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
                            if self.df_editor.mode == 'cell_insert':
                                mode = 'DF:CELL-INSERT'
                            elif self.df_editor.mode == 'cell_normal':
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
            self._set_status("No command to execute", 3)
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
            self.history_mgr.append(code)
            self.command.set_history(self.history_mgr.items)
            self.history_mgr.persist(code)
            self._set_status("Command executed", 3)
        else:
            self._set_status("Command failed", 3)

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
                self._set_status("Path required", 3)
                return
            if not (path.lower().endswith('.csv') or path.lower().endswith('.parquet')):
                self._set_status("Save failed: use .csv or .parquet", 4)
                return
            try:
                handler = FileTypeHandler(path)
                if hasattr(self.state, 'ensure_non_empty'):
                    self.state.ensure_non_empty()
                handler.save(self.state.df)
                self.state.file_handler = handler
                self.state.file_path = path
                self._set_status(f"Saved {path}", 3)
                self.save_as_active = False
                self.save_as_buffer = ""
                self.save_as_cursor = 0
                self.save_as_hscroll = 0
                if self.save_and_exit:
                    self.exit_requested = True
                self.save_and_exit = False
            except Exception as e:
                msg = f"Save failed: {e}"[: self.layout.W - 2]
                self._set_status(msg, 4)
            return

        if ch == 27:  # Esc
            self.save_as_active = False
            self.save_and_exit = False
            self.save_as_buffer = ""
            self.save_as_cursor = 0
            self.save_as_hscroll = 0
            self._set_status("Save canceled", 3)
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
            self._set_status(f"Saved {fname}" if fname else "Saved", 3)
            if save_and_exit:
                self.exit_requested = True
            return True
        except Exception as e:
            msg = f"Save failed: {e}"[: self.layout.W - 2]
            self._set_status(msg, 4)
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
                if ch == ord(':'):
                    self.command.activate()
                    self.focus = 1
                elif ch == ord('?'):
                    self._show_shortcuts()
                else:
                    self.df_editor.handle_key(ch)
            elif self.focus == 1:
                result = self.command.handle_key(ch)
                if result == "submit":
                    self._execute_command_buffer()
                elif result == "cancel":
                    self.focus = 0

            self.redraw()
            if self.exit_requested:
                break
