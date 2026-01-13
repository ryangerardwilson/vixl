import os
import shlex
import tempfile

import pandas as pd


class DfEditorExternal:
    """Handles external-editor workflows and JSON preview."""

    def __init__(self, ctx, counts, cell, push_undo_cb, set_last_action_cb):
        self.ctx = ctx
        self.counts = counts
        self.cell = cell
        self._push_undo = push_undo_cb
        self._set_last_action = set_last_action_cb

    # ---------- public entrypoints ----------
    def queue_external_edit(self, preserve_cell_mode: bool):
        if self.ctx.external_proc is not None:
            self.ctx._set_status("Already editing externally", 3)
            self.counts.reset()
            return
        if len(self.ctx.state.df.columns) == 0 or len(self.ctx.state.df) == 0:
            self.ctx._set_status("No cell to edit", 3)
            self.counts.reset()
            return

        total_rows = len(self.ctx.state.df)
        total_cols = len(self.ctx.state.df.columns)
        r = min(max(0, self.ctx.grid.curr_row), max(0, total_rows - 1))
        c = min(max(0, self.ctx.grid.curr_col), max(0, total_cols - 1))
        col = self.ctx.state.df.columns[c]

        idx_label = self.ctx.state.df.index[r] if len(self.ctx.state.df.index) > r else r
        self.ctx.pending_edit_snapshot = {
            "row": r,
            "col": c,
            "col_name": col,
            "idx_label": idx_label,
        }
        self.ctx.pending_preserve_cell_mode = preserve_cell_mode
        self.ctx.pending_external_edit = True
        self.ctx._set_status(f"Editing '{col}' at index {idx_label}", 600)
        self.counts.reset()

    def run_pending_external_edit(self):
        if not self.ctx.pending_external_edit:
            return

        snap = self.ctx.pending_edit_snapshot or {}
        r = snap.get("row", self.ctx.grid.curr_row)
        c = snap.get("col", self.ctx.grid.curr_col)
        cols = self.ctx.state.df.columns
        col_name = snap.get("col_name") or (cols[c] if len(cols) else "")

        self.ctx.pending_external_edit = False
        self.ctx.pending_edit_snapshot = None

        tmp_path, base = self._prepare_temp_file(r, c)
        if tmp_path is None:
            self.ctx._set_status("Open external editor failed", 3)
            self.ctx.pending_preserve_cell_mode = False
            return

        argv = self._build_editor_argv(tmp_path, read_only=False)
        rc = self._run_editor(argv)

        new_text = base
        try:
            with open(tmp_path, "r", encoding="utf-8") as fh:
                new_text = fh.read()
        except Exception:
            new_text = base
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        preserve_cell_mode = self.ctx.pending_preserve_cell_mode
        self.ctx.pending_preserve_cell_mode = False

        if not col_name:
            if len(self.ctx.state.df.columns) == 0:
                self.ctx._set_status("No columns to update", 3)
                return
            c = max(0, min(c, len(self.ctx.state.df.columns) - 1))
            col_name = str(self.ctx.state.df.columns[c])

        if rc not in (0, None):
            self.ctx._set_status("Edit canceled", 3)
            return

        new_text = (new_text or "").rstrip("\n")
        if new_text == base:
            self.ctx._set_status("No changes", 2)
            if preserve_cell_mode:
                self.ctx.cell_col = col_name
                self.ctx.cell_buffer = new_text
                self.ctx.cell_cursor = 0
                self.ctx.cell_hscroll = 0
                self.ctx.mode = "cell_normal"
                self.cell._autoscroll_cell_normal()
            self.counts.reset()
            return

        try:
            self._push_undo()
            coerced = self.cell._coerce_cell_value(col_name, new_text)
            self.ctx.state.df.iloc[r, c] = coerced
            self.ctx.grid.df = self.ctx.state.df
            self.ctx.paginator.update_total_rows(len(self.ctx.state.df))
            self.ctx.paginator.ensure_row_visible(r)
            self._set_last_action("cell_set", value=coerced)
            self.ctx.pending_count = None
            if preserve_cell_mode:
                self.ctx.cell_col = col_name
                self.ctx.cell_buffer = new_text
                self.ctx.cell_cursor = 0
                self.ctx.cell_hscroll = 0
                self.ctx.mode = "cell_normal"
                self.cell._autoscroll_cell_normal()
            self.ctx._set_status("Cell updated (editor)", 2)
        except Exception as exc:
            self.ctx._set_status(f"Cell update failed: {exc}", 3)
        self.counts.reset()

    def complete_external_edit_if_done(self):
        return

    def open_cell_json_preview(self, row: int, col: int):
        total_rows = len(self.ctx.state.df)
        total_cols = len(self.ctx.state.df.columns)
        if total_rows == 0 or total_cols == 0:
            self.ctx._set_status("No cell to preview", 3)
            return

        r = min(max(0, row), max(0, total_rows - 1))
        c = min(max(0, col), max(0, total_cols - 1))
        val = self.ctx.state.df.iloc[r, c]

        try:
            import json
        except ImportError:
            self.ctx._set_status("JSON preview unavailable", 3)
            return

        if val is None or (hasattr(pd, "isna") and pd.isna(val)):
            text = "null"
        else:
            try:
                parsed = json.loads(val) if isinstance(val, str) else val
                text = json.dumps(parsed, indent=2, ensure_ascii=False, default=str)
            except Exception:
                text = json.dumps(val, indent=2, ensure_ascii=False, default=str)

        tmp = tempfile.NamedTemporaryFile(mode="w+", delete=False, encoding="utf-8")
        tmp_path = tmp.name
        try:
            tmp.write(text)
            tmp.flush()
        finally:
            tmp.close()

        argv = self._build_editor_argv(tmp_path, read_only=True)
        rc = self._run_editor(argv)
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

        if rc not in (0, None):
            self.ctx._set_status("JSON preview failed", 3)
            return

        self.ctx._set_status("Opened JSON preview", 3)

    # ---------- helpers ----------
    def _prepare_temp_file(self, row_override: int, col_override: int):
        if len(self.ctx.state.df.columns) == 0 or len(self.ctx.state.df) == 0:
            return None, None

        total_rows = len(self.ctx.state.df)
        total_cols = len(self.ctx.state.df.columns)
        r = min(max(0, row_override), max(0, total_rows - 1))
        c = min(max(0, col_override), max(0, total_cols - 1))

        val = self.ctx.state.df.iloc[r, c] if total_rows > 0 else None
        base = "" if (val is None or pd.isna(val)) else str(val)

        tmp = tempfile.NamedTemporaryFile(mode="w+", delete=False, encoding="utf-8")
        tmp_path = tmp.name
        try:
            tmp.write(base)
            tmp.flush()
        finally:
            tmp.close()
        return tmp_path, base

    def _build_editor_argv(self, tmp_path: str, read_only: bool = False) -> list[str]:
        editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vim"
        argv = shlex.split(editor)
        if not argv:
            argv = ["vim"]

        ro_args: list[str] = []
        base = os.path.basename(argv[0]) if argv else ""
        if read_only and base in {"vim", "nvim"}:
            ro_args = [
                "-n",
                "-R",
                "-M",
                "+setlocal nobuflisted noswapfile buftype=nofile bufhidden=wipe nowrap readonly nomodifiable nonumber norelativenumber shortmess+=I",
            ]

        return argv + ro_args + [tmp_path]

    def _run_editor(self, argv: list[str]) -> int:
        runner = getattr(self.ctx, "run_interactive", None)
        if not callable(runner):
            self.ctx._set_status("External editor unavailable", 3)
            return 1
        try:
            return runner(argv)
        except Exception:
            return 1
