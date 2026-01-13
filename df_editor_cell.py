import curses
import pandas as pd


class DfEditorCell:
    """Handles cell editing mechanics and key handling."""

    def __init__(
        self,
        ctx,
        counts,
        push_undo_cb,
        set_last_action_cb,
        repeat_last_action_cb,
        leader_seq_cb,
        show_leader_status_cb,
        queue_external_edit_cb,
    ):
        self.ctx = ctx
        self.counts = counts
        self._push_undo = push_undo_cb
        self._set_last_action = set_last_action_cb
        self._repeat_last_action = repeat_last_action_cb
        self._leader_seq = leader_seq_cb
        self._show_leader_status = show_leader_status_cb
        self._queue_external_edit = queue_external_edit_cb

    # ---------- public entrypoint ----------
    def handle_key(self, ch: int) -> bool:
        mode = self.ctx.mode
        if mode == "cell_insert":
            self._handle_cell_insert(ch)
            return True
        if mode == "cell_normal":
            consumed = self._handle_cell_normal(ch)
            return consumed
        return False

    # ---------- cell insert mode ----------
    def _handle_cell_insert(self, ch: int) -> None:
        if ch == 27:  # Esc
            self.ctx.cell_buffer = self.ctx.cell_buffer.strip()

            r, c = self.ctx.grid.curr_row, self.ctx.grid.curr_col
            col = self.ctx.cell_col
            try:
                self._push_undo()
                val = self._coerce_cell_value(col, self.ctx.cell_buffer)
                self.ctx.state.df.iloc[r, c] = val
                self._set_last_action("cell_set", value=val)
            except Exception:
                self.ctx._set_status(f"Invalid value for column '{col}'", 3)

            # Clean reset for normal mode
            self.ctx.cell_cursor = 0
            self.ctx.cell_hscroll = 0
            self.ctx.mode = "cell_normal"
            self.counts.reset()
            return

        if ch in (curses.KEY_BACKSPACE, 127, 8):
            if self.ctx.cell_cursor > 0:
                buf = self.ctx.cell_buffer
                idx = self.ctx.cell_cursor
                self.ctx.cell_buffer = buf[: idx - 1] + buf[idx:]
                self.ctx.cell_cursor -= 1
            self._autoscroll_insert()
            return

        if 0 <= ch <= 0x10FFFF:
            try:
                ch_str = chr(ch)
            except ValueError:
                return
            buf = self.ctx.cell_buffer
            idx = self.ctx.cell_cursor
            self.ctx.cell_buffer = buf[:idx] + ch_str + buf[idx:]
            self.ctx.cell_cursor += 1
            self._autoscroll_insert()
        return

    # ---------- cell normal mode ----------
    def _handle_cell_normal(self, ch: int) -> bool:
        if ch == ord("."):
            self._repeat_last_action()
            return True

        # Numeric prefixes (counts)
        if ord("0") <= ch <= ord("9"):
            digit = ch - ord("0")
            # Leading 0 with no pending count goes to start-of-line
            if digit == 0 and self.ctx.pending_count is None:
                self.ctx.cell_cursor = 0
                self._autoscroll_cell_normal()
                return True
            self.counts.push_digit(digit)
            return True

        if self.ctx.cell_leader_state:
            state = self.ctx.cell_leader_state
            self.ctx.cell_leader_state = None
            if state == "leader":
                if ch == ord("e"):
                    # Emulate `$` then enter insert
                    self.ctx.df_leader_state = None
                    self.ctx.cell_leader_state = None
                    self.ctx.cell_cursor = len(self.ctx.cell_buffer)
                    cw = max(1, self.ctx.grid.get_rendered_col_width(self.ctx.grid.curr_col))
                    self.ctx.cell_hscroll = max(0, len(self.ctx.cell_buffer) - cw + 1)
                    self.ctx.mode = "cell_insert"
                    self.counts.reset()
                    return True
                if ch == ord("v"):
                    self._show_leader_status(",v")
                    self._queue_external_edit(preserve_cell_mode=True)
                    return True
                if ch == ord("c"):
                    self.ctx.cell_leader_state = "c"
                    self._show_leader_status(self._leader_seq("c"))
                    return True
                self._show_leader_status("")
                self.counts.reset()
                return True

            if state == "c" and ch == ord("c"):
                self.ctx.cell_buffer = ""
                self.ctx.cell_cursor = 0
                self.ctx.cell_hscroll = 0
                self.ctx.mode = "cell_insert"
                return True

        if ch == ord(","):
            self.ctx.cell_leader_state = "leader"
            return True

        buf_len = len(self.ctx.cell_buffer)
        count = self.counts.consume() if self.ctx.pending_count is not None else 1
        old_cursor = self.ctx.cell_cursor
        new_cursor = old_cursor

        if ch == ord("h"):
            new_cursor = max(0, old_cursor - count)
        elif ch == ord("l"):
            new_cursor = min(buf_len, old_cursor + count)
        elif ch == ord("0"):
            new_cursor = 0
        elif ch == ord("$"):
            new_cursor = buf_len
        elif ch == ord("w"):
            new_cursor = old_cursor
            buf = self.ctx.cell_buffer
            for _ in range(count):
                if new_cursor >= buf_len:
                    break
                self.ctx.cell_cursor = new_cursor
                next_cursor = self._cell_word_forward()
                if (
                    next_cursor >= buf_len
                    and new_cursor < buf_len
                    and buf
                    and self._is_word_char(buf[new_cursor])
                ):
                    cw = max(1, self.ctx.grid.get_rendered_col_width(self.ctx.grid.curr_col))
                    lines = max(1, getattr(self.ctx.state, "row_lines", 1))
                    span = max(1, cw * lines)
                    bounds = self._get_word_bounds_at_or_after(new_cursor)
                    if bounds:
                        _, word_end = bounds
                        visible_end = self.ctx.cell_hscroll + span
                        if word_end > visible_end:
                            max_scroll = max(0, len(self.ctx.cell_buffer) - span)
                            self.ctx.cell_hscroll = min(max_scroll, max(0, word_end - span))
                    break
                if next_cursor == new_cursor:
                    break
                new_cursor = next_cursor
        elif ch == ord("b"):
            new_cursor = old_cursor
            for _ in range(count):
                self.ctx.cell_cursor = new_cursor
                new_cursor = self._cell_word_backward()

        if new_cursor != old_cursor:
            self.ctx.cell_cursor = new_cursor
            self._autoscroll_cell_normal(prefer_left=(ch in (ord("w"), ord("b"))))
            self.counts.reset()
            return True

        self.counts.reset()

        if ch == ord("i"):
            self.ctx.mode = "cell_insert"
            return True

        if ch == 27:  # Esc
            self.ctx.mode = "normal"
            self.ctx.cell_buffer = ""
            self.ctx.cell_hscroll = 0
            return True

        return False

    # ---------- helper logic ----------
    def _coerce_cell_value(self, col_name: str, text: str):
        text = "" if text is None else str(text)
        try:
            dtype = self.ctx.state.df[col_name].dtype
        except Exception:
            dtype = object

        stripped = text.strip()
        if pd.api.types.is_integer_dtype(dtype):
            if stripped == "":
                return pd.NA
            return int(stripped)

        if pd.api.types.is_float_dtype(dtype):
            if stripped == "":
                return float("nan")
            return float(stripped)

        if pd.api.types.is_bool_dtype(dtype):
            if stripped == "":
                return pd.NA
            lowered = stripped.lower()
            if lowered in {"1", "true", "t", "yes", "y", "on"}:
                return True
            if lowered in {"0", "false", "f", "no", "n", "off"}:
                return False
            raise ValueError(f"Cannot coerce '{text}' to boolean")

        if pd.api.types.is_datetime64_any_dtype(dtype):
            if stripped == "":
                return pd.NaT
            return pd.to_datetime(stripped, errors="raise")

        return text

    def _autoscroll_insert(self):
        cw = max(1, self.ctx.grid.get_col_width(self.ctx.grid.curr_col))
        if self.ctx.cell_cursor < self.ctx.cell_hscroll:
            self.ctx.cell_hscroll = self.ctx.cell_cursor
        elif self.ctx.cell_cursor > self.ctx.cell_hscroll + cw - 1:
            self.ctx.cell_hscroll = self.ctx.cell_cursor - (cw - 1)

        max_scroll = max(0, len(self.ctx.cell_buffer) - cw + 1)
        self.ctx.cell_hscroll = max(0, min(self.ctx.cell_hscroll, max_scroll))

    def _autoscroll_cell_normal(self, prefer_left: bool = False, margin: int = 2):
        cw = max(1, self.ctx.grid.get_rendered_col_width(self.ctx.grid.curr_col))
        lines = max(1, getattr(self.ctx.state, "row_lines", 1))
        span = max(1, cw * lines)
        buf_len = len(self.ctx.cell_buffer)

        max_scroll = max(0, buf_len - span)

        if self.ctx.cell_cursor < self.ctx.cell_hscroll:
            self.ctx.cell_hscroll = self.ctx.cell_cursor
        elif self.ctx.cell_cursor >= self.ctx.cell_hscroll + span:
            if prefer_left:
                self.ctx.cell_hscroll = max(0, self.ctx.cell_cursor - max(0, margin))
            else:
                self.ctx.cell_hscroll = self.ctx.cell_cursor - span + 1

        self.ctx.cell_hscroll = min(max(self.ctx.cell_hscroll, 0), max_scroll)

    def _is_word_char(self, ch: str) -> bool:
        return ch.isalnum() or ch == "_"

    def _cell_word_forward(self):
        buf = self.ctx.cell_buffer
        n = len(buf)
        idx = self.ctx.cell_cursor
        if idx >= n:
            return n

        def is_word(i):
            return self._is_word_char(buf[i])

        if idx < n and is_word(idx):
            while idx < n and is_word(idx):
                idx += 1
        while idx < n and not is_word(idx):
            idx += 1
        return idx

    def _cell_word_backward(self):
        buf = self.ctx.cell_buffer
        if not buf or self.ctx.cell_cursor == 0:
            return 0

        def is_word(i):
            return self._is_word_char(buf[i])

        idx = max(0, self.ctx.cell_cursor - 1)
        if not is_word(idx):
            while idx > 0 and not is_word(idx):
                idx -= 1
        while idx > 0 and is_word(idx - 1):
            idx -= 1
        return idx

    def _get_word_bounds_at_or_after(self, idx: int):
        buf = self.ctx.cell_buffer
        n = len(buf)
        if n == 0:
            return None
        i = max(0, min(idx, n - 1))

        while i < n and not self._is_word_char(buf[i]):
            i += 1
        if i >= n:
            return None

        start = i
        while start > 0 and self._is_word_char(buf[start - 1]):
            start -= 1

        end = i
        while end < n and self._is_word_char(buf[end]):
            end += 1

        return start, end
