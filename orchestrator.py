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
from save_prompt import SavePrompt
from column_prompt import ColumnPrompt
from overlay import OverlayView
from shortcut_help_handler import ShortcutHelpHandler


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

        # ---- overlay ----
        self.overlay = OverlayView(self.layout)

        # ---- save-as prompt ----
        self.save_prompt = SavePrompt(self.state, FileTypeHandler, self._set_status)

        # ---- column prompt ----
        self.column_prompt = ColumnPrompt(
            self.state, self.grid, self.paginator, self._set_status
        )
        self.exit_requested = False

        # ---- status ----
        self.status_msg = None
        self.status_msg_until = 0

        # ---- history ----
        legacy_path = os.path.expanduser("~/.vixl_history")
        self.history_mgr = HistoryManager(
            HISTORY_PATH, legacy_path=legacy_path, max_items=100
        )
        self.history = self.history_mgr.load()

        # share history with command pane
        self.command.set_history(self.history)

        # ---- DF editor ----
        self.df_editor = DfEditor(
            self.state, self.grid, self.paginator, self._set_status, self.column_prompt
        )
        # wire undo into column prompt
        if hasattr(self.column_prompt, "set_push_undo"):
            self.column_prompt.set_push_undo(self.df_editor._push_undo)

    # ---------------- helpers ----------------

    def _set_status(self, msg, seconds=3):
        self.status_msg = msg
        self.status_msg_until = time.time() + seconds

    # ---------------- UI ----------------

    def redraw(self):
        try:
            if self.overlay.visible:
                curses.curs_set(0)
            elif self.save_prompt.active or self.column_prompt.active:
                curses.curs_set(1)
            else:
                curses.curs_set(1 if (self.focus == 1 and self.command.active) else 0)
        except curses.error:
            pass

        if not self.overlay.visible:
            self.grid.draw(
                self.layout.table_win,
                active=(self.focus == 0),
                editing=(
                    self.focus == 0
                    and self.df_editor.mode in ("cell_insert", "cell_normal")
                ),
                insert_mode=(self.focus == 0 and self.df_editor.mode == "cell_insert"),
                edit_row=self.grid.curr_row,
                edit_col=self.grid.curr_col,
                edit_buffer=self.df_editor.cell_buffer,
                edit_cursor=self.df_editor.cell_cursor,
                edit_hscroll=self.df_editor.cell_hscroll,
                page_start=self.paginator.page_start,
                page_end=self.paginator.page_end,
                row_lines=self.state.row_lines,
            )

            sw = self.layout.status_win
            sw.erase()
            h, w = sw.getmaxyx()

            if self.column_prompt.active:
                self.column_prompt.draw(sw)
            elif self.save_prompt.active:
                self.save_prompt.draw(sw)
            else:
                cmd_active = self.focus == 1 and self.command.active

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
                            if self.df_editor.mode == "cell_insert":
                                mode = "DF:CELL-INSERT"
                            elif self.df_editor.mode == "cell_normal":
                                mode = "DF:CELL-NORMAL"
                            else:
                                mode = "DF"
                        elif self.focus == 1:
                            mode = "CMD"
                        else:
                            mode = "DF"
                        fname = (
                            os.path.basename(self.state.file_path)
                            if self.state.file_path
                            else ""
                        )
                        shape = f"{self.state.df.shape}"
                        page_total = self.paginator.page_count
                        page_info = f"Page {self.paginator.page_index + 1}/{page_total} rows {self.paginator.page_start}-{max(self.paginator.page_start, self.paginator.page_end - 1)} of {self.paginator.total_rows}"
                        count_text = ""
                        if self.focus == 0 and getattr(
                            self.df_editor, "pending_count", None
                        ):
                            count_val = self.df_editor.pending_count
                            count_text = f" | Count: {count_val}"
                        text = f" {mode} | {fname} | {shape} | {page_info}{count_text}"

                    try:
                        sw.addnstr(0, 0, text.ljust(w), w)
                    except curses.error:
                        pass
                    sw.refresh()

        if self.overlay.visible:
            self.overlay.draw()

    # ---------------- command exec ----------------

    def _execute_command_buffer(self):
        code = self.command.get_buffer().strip()

        if not code:
            self.command.reset()
            self.focus = 0
            self._set_status("No command to execute", 3)
            return

        lines = self.exec.execute(code)
        if lines:
            self.overlay.open(lines)
            self.focus = 2
        else:
            self.overlay.close()
            self.focus = 0

        # clear command bar after execution
        self.command.reset()

        # sync grid with latest df and clamp cursor within bounds
        self.grid.df = self.state.df
        self.paginator.update_total_rows(len(self.state.df))
        self.grid.curr_row = min(self.grid.curr_row, max(0, len(self.grid.df) - 1))
        self.grid.curr_col = min(
            self.grid.curr_col, max(0, len(self.grid.df.columns) - 1)
        )
        self.paginator.ensure_row_visible(self.grid.curr_row)

        if getattr(self.exec, "_last_success", False):
            self.history_mgr.append(code)
            self.command.set_history(self.history_mgr.items)
            self.history_mgr.persist(code)
            self._set_status("Command executed", 3)
        else:
            self._set_status("Command failed", 3)

    # ---------------- saving ----------------

    def _save_df(self, save_and_exit=False):
        handler = getattr(self.state, "file_handler", None)
        if handler is None:
            self.save_prompt.start(self.state.file_path, save_and_exit=save_and_exit)
            self.focus = 0
            return False

        try:
            if hasattr(self.state, "ensure_non_empty"):
                self.state.ensure_non_empty()
            handler.save(self.state.df)
            fname = self.state.file_path or ""
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

            if self.overlay.visible:
                self.overlay.handle_key(ch)
                if not self.overlay.visible:
                    self.focus = 0
                self.redraw()
                continue

            if self.column_prompt.active:
                self.column_prompt.handle_key(ch)
                if not self.column_prompt.active:
                    self.focus = 0
                self.redraw()
                continue

            if self.save_prompt.active:
                self.save_prompt.handle_key(ch)
                if self.save_prompt.exit_requested:
                    self.exit_requested = True
                if not self.save_prompt.active:
                    self.focus = 0
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
                if ch == ord(":"):
                    self.command.activate()
                    self.focus = 1
                elif ch == ord("?"):
                    self.overlay.open(ShortcutHelpHandler.get_lines())
                    self.focus = 2
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
