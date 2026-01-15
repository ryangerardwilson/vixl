# ~/Apps/vixl/orchestrator.py
import curses
import time
import os
import subprocess
import re
import difflib

from grid_pane import GridPane
from command_pane import CommandPane
from command_executor import CommandExecutor
from screen_layout import ScreenLayout
from config_paths import HISTORY_PATH, ensure_config_dirs
from expression_register import parse_expression_register
from file_type_handler import FileTypeHandler
from pagination import Paginator
from history_manager import HistoryManager
from df_editor import DfEditor
from save_prompt import SavePrompt
from column_prompt import ColumnPrompt
from overlay import OverlayView
from shortcut_help_handler import ShortcutHelpHandler


_PUNCT_TO_SPACE = re.compile(r"[\(\)\[\]\{\},.:/+=-]")
_WHITESPACE = re.compile(r"\s+")
_VOWELS = re.compile(r"[aeiou]")


def _normalize_text(text):
    if not isinstance(text, str):
        return ""
    lowered = text.lower()
    lowered = _PUNCT_TO_SPACE.sub(" ", lowered)
    lowered = _WHITESPACE.sub(" ", lowered).strip()
    return lowered


def _skeleton_word(word):
    return _VOWELS.sub("", word)


def _skeleton_text(text):
    words = _normalize_text(text).split()
    return " ".join(_skeleton_word(w) for w in words)


def _is_subsequence(needle, haystack):
    it = iter(haystack)
    for ch in needle:
        for val in it:
            if val == ch:
                break
        else:
            return False
    return True


def _token_score(q_word, c_word):
    qs = _skeleton_word(q_word)
    cs = _skeleton_word(c_word)
    if not qs or not cs:
        return 0.0

    score = 0.0
    if cs.startswith(qs):
        score = 1.0
    elif _is_subsequence(qs, cs):
        score = 0.7

    # If the non-skeletonized words also prefix-match, honor that strongly.
    ql = q_word.lower()
    cl = c_word.lower()
    if cl.startswith(ql):
        score = max(score, 0.9)
    return score


def _phrase_score(q_words, c_words):
    m = len(q_words)
    n = len(c_words)
    if m == 0 or n == 0 or m > n:
        return 0.0

    best = 0.0
    for i in range(n - m + 1):
        window = c_words[i : i + m]
        scores = [_token_score(qw, cw) for qw, cw in zip(q_words, window)]
        avg = sum(scores) / m if m else 0.0
        if avg > best:
            best = avg
    return best


def _fuzzy_best_text_match(query, texts):
    if not isinstance(query, str):
        return None
    normalized_query = _normalize_text(query)
    if not normalized_query:
        return None

    q_words = normalized_query.split()
    q_skel = _skeleton_text(query)
    best_index = None
    best_score = -1.0
    best_phrase = -1.0
    best_len = None

    for idx, text in enumerate(texts or []):
        if not isinstance(text, str):
            continue
        if not text.strip():
            continue
        norm_cand = _normalize_text(text)
        if not norm_cand:
            continue
        c_words = norm_cand.split()
        c_skel = _skeleton_text(text)

        overall = difflib.SequenceMatcher(None, q_skel, c_skel).ratio()
        phrase = _phrase_score(q_words, c_words)

        score = 0.7 * overall + 0.3 * phrase
        if phrase >= 0.92:
            score = max(score, 0.9 * phrase)

        cand_len = len(text)
        if (
            score > best_score
            or (
                score == best_score
                and (
                    phrase > best_phrase
                    or (
                        phrase == best_phrase
                        and (best_len is None or cand_len < best_len)
                    )
                )
            )
        ):
            best_score = score
            best_phrase = phrase
            best_len = cand_len
            best_index = idx

    return best_index


def fuzzy_best_match(query, entries):
    valid_pairs = []
    for entry in entries or []:
        match_text = getattr(entry, "match_text", None)
        if isinstance(match_text, str) and match_text.strip():
            valid_pairs.append((entry, match_text))
    if not valid_pairs:
        return None
    idx = _fuzzy_best_text_match(query, [text for _, text in valid_pairs])
    if idx is None:
        return None
    return valid_pairs[idx][0]


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
        if hasattr(self.command, "set_extension_names"):
            self.command.set_extension_names(self.exec.get_extension_names())
        if hasattr(self.command, "set_expression_register"):
            self.command.set_expression_register(
                self.exec.config.get("EXPRESSION_REGISTER", [])
            )

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

        if code.startswith("%fz#/"):
            query = code[len("%fz#/") :].strip()
            raw_register = self.exec.config.get("EXPRESSION_REGISTER", [])
            entries = parse_expression_register(raw_register)
            if not query:
                self._set_status("Query required", 3)
                return
            if not entries:
                self._set_status("Expression register empty", 3)
                return
            comment_texts = []
            comment_entries = []
            for entry in entries:
                comment = getattr(entry, "comment", "").strip()
                if comment:
                    comment_texts.append(comment)
                    comment_entries.append(entry)
            if not comment_entries:
                self._set_status("No commented entries", 3)
                return
            idx = _fuzzy_best_text_match(query, comment_texts)
            if idx is None:
                self._set_status(f"No comment match for: {query}", 3)
                return
            best_entry = comment_entries[idx]
            if getattr(best_entry, "kind", "expression") == "comment_only":
                self._set_status("Matched comment-only entry", 3)
                return
            expr = getattr(best_entry, "expr", "").strip()
            if not expr:
                self._set_status("No expression to load", 3)
                return
            self.command.set_buffer(expr)
            self.focus = 1
            self._set_status(f"Loaded: {expr}", 3)
            return

        if code.startswith("%fz/"):
            query = code[len("%fz/") :].strip()
            raw_register = self.exec.config.get("EXPRESSION_REGISTER", [])
            entries = parse_expression_register(raw_register)
            if not query:
                self._set_status("Query required", 3)
                return
            if not entries:
                self._set_status("Expression register empty", 3)
                return
            best_entry = fuzzy_best_match(query, entries)
            if not best_entry:
                self._set_status(f"No match for: {query}", 3)
                return
            if getattr(best_entry, "kind", "expression") == "comment_only":
                self._set_status("Matched comment-only entry", 3)
                return
            expr = getattr(best_entry, "expr", "").strip()
            if not expr:
                self._set_status("No expression to load", 3)
                return
            self.command.set_buffer(expr)
            self.focus = 1
            self._set_status(f"Loaded: {expr}", 3)
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

            if getattr(self, "df_editor", None) is not None:
                self.df_editor._complete_external_edit_if_done()
                self.df_editor.run_pending_external_edit()

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

            if getattr(self, "df_editor", None) is not None:
                self.df_editor.run_pending_external_edit()

            self.redraw()

            if self.exit_requested:
                break
