import os
import shlex
import subprocess
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
        if self.ctx.external_proc is not None:
            return

        snap = self.ctx.pending_edit_snapshot or {}
        r = snap.get("row", self.ctx.grid.curr_row)
        c = snap.get("col", self.ctx.grid.curr_col)
        cols = self.ctx.state.df.columns
        col_name = snap.get("col_name") or (cols[c] if len(cols) else "")

        self.ctx.pending_external_edit = False
        self.ctx.pending_edit_snapshot = None

        proc, tmp_path, base = self._start_external_edit_process(r, c, col_name)
        if proc is None:
            self.ctx._set_status("Open in Alacritty failed", 3)
            self.ctx.pending_preserve_cell_mode = False
            return

        self.ctx.external_proc = proc
        self.ctx.external_tmp_path = tmp_path
        self.ctx.external_meta = {
            "row": r,
            "col": c,
            "col_name": col_name,
            "base": base,
            "preserve_cell_mode": self.ctx.pending_preserve_cell_mode,
        }
        self.ctx.pending_preserve_cell_mode = False

    def complete_external_edit_if_done(self):
        proc = self.ctx.external_proc
        if proc is None:
            return
        if proc.poll() is None:
            return

        if not self.ctx.external_receiving:
            self.ctx.external_receiving = True
            self.ctx._set_status("Receiving new data from editor", 5)
            return

        rc = proc.returncode
        tmp_path = self.ctx.external_tmp_path
        meta = self.ctx.external_meta or {}

        self.ctx.external_proc = None
        self.ctx.external_tmp_path = None
        self.ctx.external_meta = None
        self.ctx.external_receiving = False

        base = meta.get("base", "")
        r = meta.get("row", self.ctx.grid.curr_row)
        c = meta.get("col", self.ctx.grid.curr_col)
        preserve_cell_mode = meta.get("preserve_cell_mode", False)

        col_name_raw = meta.get("col_name")
        if isinstance(col_name_raw, str) and col_name_raw:
            col_name = col_name_raw
        else:
            if len(self.ctx.state.df.columns) == 0:
                self.ctx._set_status("No columns to update", 3)
                return
            c = max(0, min(c, len(self.ctx.state.df.columns) - 1))
            col_name = str(self.ctx.state.df.columns[c])

        new_text = base
        if tmp_path:
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

        editor_cmd = self._build_editor_command(tmp_path, read_only=True)
        proc = self._launch_in_alacritty(editor_cmd)
        if proc is None:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
            self.ctx._set_status("JSON preview failed", 3)
            return

        self.ctx._set_status("Opened JSON preview (read-only)", 3)

    # ---------- helpers ----------
    def _start_external_edit_process(self, row_override: int, col_override: int, col_name: str):
        if len(self.ctx.state.df.columns) == 0 or len(self.ctx.state.df) == 0:
            return None, None, None

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

        editor_cmd = self._build_editor_command(tmp_path)
        proc = self._launch_in_alacritty(editor_cmd)
        if proc is None:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
            return None, None, None
        return proc, tmp_path, base

    def _build_editor_command(self, tmp_path: str, read_only: bool = False) -> str:
        editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vim"
        if read_only:
            ro_opts = (
                "-n -R -M "
                "+setlocal\ nobuflisted\ noswapfile\ buftype=nofile\ bufhidden=wipe\ "
                "nowrap\ readonly\ nomodifiable\ nonumber\ norelativenumber\ shortmess+=I"
            )
            return f"{editor} {ro_opts} {shlex.quote(tmp_path)}"
        return f"{editor} {shlex.quote(tmp_path)}"

    def _launch_in_alacritty(self, editor_cmd: str):
        try:
            proc = subprocess.Popen(["alacritty", "-e", "bash", "-lc", editor_cmd])
            return proc
        except FileNotFoundError:
            return None
        except Exception:
            return None
