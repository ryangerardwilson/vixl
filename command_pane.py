import curses


class CommandPane:
    def __init__(self):
        self.buffer = ""
        self.cursor = 0
        self.hscroll = 0
        self.active = False
        self.history = []
        self.history_idx = None  # None means not navigating history
        self.extension_names = []
        self.expression_register_entries = []
        self.meta_pending = False
        self.ghost_attr = curses.A_DIM
        try:
            curses.start_color()
            curses.use_default_colors()
            # Light foreground on default background so ghost text remains visible
            fg = curses.COLOR_WHITE
            bg = -1
            curses.init_pair(9, fg, bg)
            self.ghost_attr = curses.color_pair(9) | curses.A_DIM
        except curses.error:
            self.ghost_attr = curses.A_DIM

    # ---------- state helpers ----------
    def reset(self):
        self.buffer = ""
        self.cursor = 0
        self.hscroll = 0
        self.active = False
        self.history_idx = None

    def activate(self):
        self.active = True
        self.cursor = max(0, min(self.cursor, len(self.buffer)))
        self.history_idx = None

    def get_buffer(self):
        return self.buffer

    def set_buffer(self, text):
        self.buffer = text or ""
        self.cursor = len(self.buffer)
        self.hscroll = 0
        self.history_idx = None

    def set_history(self, entries):
        self.history = list(entries or [])
        self.history_idx = None

    def set_extension_names(self, names):
        self.extension_names = sorted(names or [])
        self.hscroll = min(self.hscroll, max(0, len(self.buffer)))

    def set_expression_register(self, expressions):
        try:
            from expression_register import parse_expression_register
        except ImportError:
            parse_expression_register = lambda entries: []
        self.expression_register_entries = parse_expression_register(expressions)
        self.hscroll = min(self.hscroll, max(0, len(self.buffer)))

    def _apply_history(self):
        if self.history_idx is None:
            return
        if 0 <= self.history_idx < len(self.history):
            self.buffer = self.history[self.history_idx]
        else:
            self.buffer = ""
        self.cursor = len(self.buffer)
        self.hscroll = 0

    # ---------- completion helpers ----------
    def _extract_df_token(self):
        prefix = self.buffer[: self.cursor]
        after = self.buffer[self.cursor :]
        if after and (after[0].isalnum() or after[0] == "_"):
            return None

        markers = ["df.vixl.", "df."]
        chosen = None
        for marker in markers:
            idx = prefix.rfind(marker)
            if idx != -1:
                if (
                    chosen is None
                    or idx > chosen[0]
                    or (idx == chosen[0] and len(marker) > len(chosen[1]))
                ):
                    chosen = (idx, marker)
        if not chosen:
            return None

        idx, marker = chosen
        token = prefix[idx + len(marker) :]
        if len(token) == 0:
            return None
        if not all(ch.isalnum() or ch == "_" for ch in token):
            return None

        return (idx + len(marker), self.cursor, token, marker)

    def _choose_expression_register_suggestion(self, token, marker):
        if not token or not self.expression_register_entries:
            return None

        candidates = []
        for entry in self.expression_register_entries:
            if getattr(entry, "kind", None) != "expression":
                continue
            expr = getattr(entry, "expr", "")
            if not expr.startswith(marker):
                continue
            tail = expr[len(marker) :]
            candidates.append(tail)

        prefix_matches = [c for c in candidates if c.startswith(token)]
        if prefix_matches:
            prefix_matches.sort(key=lambda x: (len(x), x))
            chosen = prefix_matches[0]
            display = chosen[len(token) :]
            return chosen, display
        return None

    def _choose_extension_suggestion(self, token, marker):
        if marker != "df.vixl." or not token or not self.extension_names:
            return None

        prefix_matches = [
            name for name in self.extension_names if name.startswith(token)
        ]
        if prefix_matches:
            prefix_matches.sort(key=lambda x: (len(x), x))
            chosen = prefix_matches[0]
            display = chosen[len(token) :]
            return chosen, display
        return None

    def _get_suggestion(self):
        token_info = self._extract_df_token()
        if not token_info:
            return None
        start, end, token, marker = token_info

        suggestion = self._choose_expression_register_suggestion(token, marker)
        if not suggestion:
            suggestion = self._choose_extension_suggestion(token, marker)
        if not suggestion:
            return None

        chosen, display = suggestion
        return {
            "replacement": chosen,
            "display": display,
            "start": start,
            "end": end,
            "marker": marker,
        }

    def _apply_suggestion(self, suggestion):
        token_start = suggestion["start"]
        token_end = suggestion["end"]
        replacement = suggestion["replacement"]
        self.buffer = self.buffer[:token_start] + replacement + self.buffer[token_end:]

        self.cursor = token_start + len(replacement)

        self.hscroll = min(self.hscroll, max(0, self.cursor))
        self.history_idx = None

    # ---------- word helpers ----------
    @staticmethod
    def _is_word_char(ch):
        return ch.isalnum() or ch == "_"

    def _word_boundary_left(self):
        i = self.cursor
        # skip whitespace immediately left
        while i > 0 and self.buffer[i - 1].isspace():
            i -= 1
        # skip closing punctuation immediately left of the cursor
        while (
            i > 0
            and not self._is_word_char(self.buffer[i - 1])
            and not self.buffer[i - 1].isspace()
        ):
            i -= 1
        # skip the word directly left of the cursor
        while i > 0 and self._is_word_char(self.buffer[i - 1]):
            i -= 1
        # include a single punctuation character that directly precedes the word (e.g., opening paren)
        if (
            i > 0
            and not self._is_word_char(self.buffer[i - 1])
            and not self.buffer[i - 1].isspace()
        ):
            i -= 1

        boundary = i

        # consume whitespace separating the previous chunk
        while boundary > 0 and self.buffer[boundary - 1].isspace():
            boundary -= 1

        # if the chunk is preceded by punctuation, treat the preceding word as part of it
        lookahead = boundary
        while lookahead > 0 and self._is_word_char(self.buffer[lookahead - 1]):
            lookahead -= 1

        if (
            lookahead < boundary
            and lookahead > 0
            and not self._is_word_char(self.buffer[lookahead - 1])
            and not self.buffer[lookahead - 1].isspace()
        ):
            return lookahead

        return boundary

    def _word_boundary_right(self):
        i = self.cursor
        n = len(self.buffer)
        # skip separators immediately right
        while i < n and not self._is_word_char(self.buffer[i]):
            i += 1
        # skip the word
        while i < n and self._is_word_char(self.buffer[i]):
            i += 1
        # include any immediate whitespace
        while i < n and self.buffer[i].isspace():
            i += 1
        # include a single trailing punctuation character (e.g., closing paren)
        while (
            i < n
            and not self._is_word_char(self.buffer[i])
            and not self.buffer[i].isspace()
            and i > 0
            and self._is_word_char(self.buffer[i - 1])
        ):
            i += 1
        return i

    # ---------- input handling ----------
    def handle_key(self, ch):
        if not self.active:
            return None

        # handle pending meta (Alt) sequences
        if self.meta_pending:
            self.meta_pending = False
            if ch in (ord("f"), ord("F")):
                self.cursor = self._word_boundary_right()
                return None
            if ch in (ord("b"), ord("B")):
                self.cursor = self._word_boundary_left()
                return None
            # treat as plain Esc cancel if unknown sequence
            self.reset()
            return "cancel"

        # history navigation
        if ch == 16:  # Ctrl+P
            if self.history:
                if self.history_idx is None:
                    self.history_idx = len(self.history) - 1
                else:
                    self.history_idx = max(0, self.history_idx - 1)
                self._apply_history()
            return None
        if ch == 14:  # Ctrl+N
            if self.history:
                if self.history_idx is None:
                    # stay at blank
                    self.buffer = ""
                    self.cursor = 0
                    self.hscroll = 0
                else:
                    self.history_idx += 1
                    if self.history_idx >= len(self.history):
                        self.history_idx = None
                        self.buffer = ""
                        self.cursor = 0
                        self.hscroll = 0
                    else:
                        self._apply_history()
            return None

        if ch == 9:  # Tab
            suggestion = self._get_suggestion()
            if suggestion:
                self._apply_suggestion(suggestion)
            return None

        # submit
        if ch in (10, 13):  # Enter
            return "submit"

        # cancel / meta prefix
        if ch == 27:  # Esc
            self.meta_pending = True
            return None

        if ch == 23:  # Ctrl+W, delete word backward
            start = self._word_boundary_left()
            if start < self.cursor:
                self.buffer = self.buffer[:start] + self.buffer[self.cursor :]
                self.cursor = start
                self.history_idx = None
            return None

        if ch == 21:  # Ctrl+U, kill to line start
            if self.cursor > 0:
                self.buffer = self.buffer[self.cursor :]
                self.cursor = 0
                self.history_idx = None
            return None

        if ch in (curses.KEY_BACKSPACE, 127):
            if self.cursor > 0:
                self.buffer = (
                    self.buffer[: self.cursor - 1] + self.buffer[self.cursor :]
                )
                self.cursor -= 1
            self.history_idx = None
            return None

        if ch == 8:  # Ctrl+H, move left
            self.cursor = max(0, self.cursor - 1)
            return None

        if ch == 4:  # Ctrl+D, move right
            self.cursor = min(len(self.buffer), self.cursor + 1)
            return None

        if ch == curses.KEY_LEFT:
            self.cursor = max(0, self.cursor - 1)
            return None

        if ch == curses.KEY_RIGHT:
            self.cursor = min(len(self.buffer), self.cursor + 1)
            return None

        if ch in (curses.KEY_HOME, 1):  # Home or Ctrl+A
            self.cursor = 0
            return None

        if ch in (curses.KEY_END, 5):  # End or Ctrl+E
            self.cursor = len(self.buffer)
            return None

        if 32 <= ch <= 126:
            self.buffer = (
                self.buffer[: self.cursor] + chr(ch) + self.buffer[self.cursor :]
            )
            self.cursor += 1
            self.history_idx = None
            return None

        return None

    # ---------- rendering ----------
    def draw(self, win, active=False):
        win.erase()
        h, w = win.getmaxyx()
        prompt = ":"
        text_w = max(1, w - len(prompt) - 1)

        # adjust scroll to keep cursor visible
        if self.cursor < self.hscroll:
            self.hscroll = self.cursor
        elif self.cursor > self.hscroll + text_w:
            self.hscroll = self.cursor - text_w

        slice_start = self.hscroll
        slice_end = slice_start + text_w
        visible = self.buffer[slice_start:slice_end]

        try:
            win.addnstr(0, 0, prompt, len(prompt))
            win.addnstr(0, len(prompt), visible, text_w)
        except curses.error:
            pass

        if self.active:
            suggestion = self._get_suggestion()
            if suggestion:
                display = suggestion.get("display", "") or ""
                cursor_col = self.cursor - self.hscroll
                if display and 0 <= cursor_col < text_w:
                    ghost_start = len(prompt) + cursor_col
                    remaining = text_w - cursor_col
                    ghost_text = display[:remaining]
                    try:
                        win.addnstr(
                            0, ghost_start, ghost_text, remaining, self.ghost_attr
                        )
                    except curses.error:
                        pass

        if active and self.active:
            cx = len(prompt) + (self.cursor - self.hscroll)
            cy = 0
            try:
                win.move(cy, max(0, min(cx, w - 1)))
            except curses.error:
                pass

        win.refresh()
