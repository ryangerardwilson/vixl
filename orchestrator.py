# ~/Apps/vixl/orchestrator.py
import curses
import time
import os
import subprocess

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
        if getattr(self.exec, "startup_warnings", None):
            self._set_status(self.exec.startup_warnings[0], seconds=6)

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
        # allow external editor to run in current terminal
        if hasattr(self.df_editor, "ctx"):
            self.df_editor.ctx.run_interactive = self._run_interactive_in_terminal
            self.df_editor.ctx.config = getattr(self.exec, "config", {})
            self.df_editor.ctx.refresh_config = self._reload_config
        # wire undo into column prompt
        if hasattr(self.column_prompt, "set_push_undo"):
            self.column_prompt.set_push_undo(self.df_editor._push_undo)

    # ---------------- helpers ----------------

    def _run_interactive_in_terminal(self, argv):
        if not argv:
            return 1
        try:
            curses.def_prog_mode()
        except curses.error:
            pass
        try:
            curses.endwin()
        except curses.error:
            pass

        try:
            result = subprocess.run(argv).returncode
        except FileNotFoundError:
            result = 127
        except Exception:
            result = 1

        try:
            curses.reset_prog_mode()
        except curses.error:
            pass
        try:
            curses.raw()
            self.stdscr.nodelay(False)
            self.stdscr.timeout(100)
        except curses.error:
            pass
        try:
            self.stdscr.clear()
            self.stdscr.refresh()
            self.redraw()
        except Exception:
            pass
        return result

    def _reload_config(self):
        try:
            ignored = self.exec.reload_config()
        except Exception as exc:
            self._set_status(f"Config reload failed: {exc}", 4)
            return

        cfg = self.exec.config

        if hasattr(self.df_editor, "ctx"):
            self.df_editor.ctx.config = cfg

        self._set_status("Config reloaded", 4)

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
                page_start=self.paginator.page_start,
                page_end=self.paginator.page_end,
                row_lines=self.state.row_lines,
                expanded_rows=self.state.expanded_rows,
                expand_all_rows=self.state.expand_all_rows,
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
                            mode = (
                                "VISUAL"
                                if getattr(self.grid, "visual_active", False)
                                else "DF"
                            )
                        elif self.focus == 1:
                            mode = "CMD"
                        else:
                            mode = "DF"
                        fname = (
                            os.path.basename(self.state.file_path)
                            if self.state.file_path
                            else ""
                        )
                        sheet_text = ""
                        if getattr(self.state, "has_sheets", lambda: False)():
                            sheet_name = getattr(self.state, "active_sheet", None)
                            sheet_order = getattr(self.state, "sheet_order", [])
                            if sheet_name and sheet_order:
                                try:
                                    sheet_idx = sheet_order.index(sheet_name) + 1
                                except ValueError:
                                    sheet_idx = 1
                                sheet_total = len(sheet_order)
                                sheet_text = f" | Sheet {sheet_idx}/{sheet_total}"
                        shape = f"{self.state.df.shape}"
                        page_total = self.paginator.page_count
                        row_start = self.paginator.page_start
                        row_end = max(
                            self.paginator.page_start, self.paginator.page_end - 1
                        )
                        page_info = (
                            f"Page {self.paginator.page_index + 1}/{page_total}"
                            f" | Rows {row_start}-{row_end}/{self.paginator.total_rows}"
                        )
                        count_text = ""
                        if self.focus == 0 and getattr(
                            self.df_editor, "pending_count", None
                        ):
                            count_val = self.df_editor.pending_count
                            count_text = f" | Count: {count_val}"
                        text = f" {mode} | {fname}{sheet_text} | {shape} | {page_info}{count_text}"

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
            self.overlay.open_output(lines)
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
            payload = self.state.df
            if getattr(handler, "ext", None) in {".xlsx", ".h5"} and getattr(
                self.state, "sheets", None
            ):
                payload = self.state.sheets
            handler.save(payload)
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

            if getattr(self, "df_editor", None) is not None:
                self.df_editor._complete_external_edit_if_done()
                self.df_editor.run_pending_external_edit()

            if ch in (3, 17):
                break

            if ch in (ord("q"), ord("Q")) and self.focus == 0:
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

            if ch in (3, 17):
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
                    # exit visual mode if active
                    if getattr(self, "df_editor", None) is not None and hasattr(
                        self.df_editor.ctx, "visual_active"
                    ):
                        self.df_editor.ctx.visual_active = False
                        self.df_editor.ctx.visual_anchor = None
                        if hasattr(self.grid, "visual_active"):
                            self.grid.visual_active = False
                        if hasattr(self.grid, "visual_rect"):
                            self.grid.visual_rect = None
                    self.command.activate()
                    self.focus = 1
                elif ch == ord("?"):
                    self.overlay.open_help(ShortcutHelpHandler.get_lines())
                    self.focus = 2
                else:
                    self.df_editor.handle_key(ch)
            elif self.focus == 1:
                result = self.command.handle_key(ch)
                if result == "submit":
                    self._execute_command_buffer()
                elif result == "cancel":
                    self.focus = 0

            if getattr(self, "df_editor", None) is not None:
                self.df_editor.run_pending_external_edit()

            self.redraw()

            if self.exit_requested:
                break
