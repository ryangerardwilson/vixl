import os
import tempfile

import pandas as pd

from cell_coercion import coerce_cell_value
from config_paths import CONFIG_JSON, ensure_config_dirs


class DfEditorExternal:
    """Handles external-editor workflows and JSON preview."""

    def __init__(self, ctx, counts, push_undo_cb, set_last_action_cb):
        self.ctx = ctx
        self.counts = counts
        self._push_undo = push_undo_cb
        self._set_last_action = set_last_action_cb

    # ---------- public entrypoints ----------
    def queue_external_edit(self):
        if self.ctx.pending_external_edit:
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

        idx_label = (
            self.ctx.state.df.index[r] if len(self.ctx.state.df.index) > r else r
        )
        self.ctx.pending_edit_snapshot = {
            "row": r,
            "col": c,
            "col_name": col,
            "idx_label": idx_label,
        }
        self.ctx.pending_external_edit = True
        self.ctx.pending_external_kind = "cell"
        self.ctx._set_status(f"Editing '{col}' at index {idx_label}", 600)
        self.counts.reset()

    def queue_visual_fill(self, rect):
        if self.ctx.pending_external_edit:
            self.ctx._set_status("Already editing externally", 3)
            self.counts.reset()
            return
        if len(self.ctx.state.df.columns) == 0 or len(self.ctx.state.df) == 0:
            self.ctx._set_status("No cells to fill", 3)
            self.counts.reset()
            return
        if not rect:
            self.ctx._set_status("No selection", 3)
            self.counts.reset()
            return
        r0, r1, c0, c1 = rect
        rows = max(0, r1 - r0 + 1)
        cols = max(0, c1 - c0 + 1)
        self.ctx.pending_edit_snapshot = {
            "kind": "visual_fill",
            "rect": (r0, r1, c0, c1),
        }
        self.ctx.pending_external_edit = True
        self.ctx.pending_external_kind = "visual_fill"
        self.ctx._set_status(f"Fill {rows}x{cols} cells (editor)", 600)
        self.counts.reset()

    def open_config(self):
        ensure_config_dirs()
        config_path = CONFIG_JSON
        created = False
        if not os.path.exists(config_path):
            try:
                with open(config_path, "w", encoding="utf-8") as fh:
                    fh.write(self._default_config_contents())
                created = True
            except Exception as exc:
                self.ctx._set_status(f"Config open failed: {exc}", 3)
                self.counts.reset()
                return

        argv = self._build_editor_argv(config_path, read_only=False)
        rc = self._run_editor(argv)
        if rc not in (0, None):
            msg = "Config edit canceled"
            if created:
                msg = f"Config edit canceled (created at {config_path})"
            self.ctx._set_status(msg, 3)
        else:
            self.ctx._set_status(f"Opened config at {config_path}", 3)
            refresh_cb = getattr(self.ctx, "refresh_config", None)
            if callable(refresh_cb):
                try:
                    refresh_cb()
                except Exception as exc:
                    self.ctx._set_status(f"Config reload failed: {exc}", 3)
        self.counts.reset()

    def _trim_editor_text(self, text) -> str:
        if text is None:
            return ""
        normalized = str(text).replace("\r\n", "\n").replace("\r", "\n")
        return normalized.strip()

    def run_pending_external_edit(self):
        if not self.ctx.pending_external_edit:
            return

        snap = self.ctx.pending_edit_snapshot or {}
        kind = snap.get("kind") or getattr(self.ctx, "pending_external_kind", "cell")

        # Reset pending flags early to avoid reentrancy
        self.ctx.pending_external_edit = False
        self.ctx.pending_external_kind = None
        self.ctx.pending_edit_snapshot = None

        if kind == "visual_fill":
            rect = snap.get("rect")
            if not rect:
                self.ctx._set_status("No selection", 3)
                return
            r0, r1, c0, c1 = rect
            tmp = tempfile.NamedTemporaryFile(mode="w+", delete=False, encoding="utf-8")
            tmp_path = tmp.name
            base = ""
            try:
                tmp.write(base)
                tmp.flush()
            finally:
                tmp.close()

            argv = self._build_editor_argv(tmp_path, read_only=False)
            rc = self._run_editor(argv)

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
                self.ctx._set_status("Fill canceled", 3)
                return

            new_text = self._trim_editor_text(new_text)
            if new_text == base:
                self.ctx._set_status("No changes", 2)
                self.counts.reset()
                return

            # Validate coercion per column first
            coerced_per_col = {}
            try:
                for cc in range(c0, c1 + 1):
                    col_name = self.ctx.state.df.columns[cc]
                    coerced_per_col[cc] = coerce_cell_value(
                        self.ctx.state.df, col_name, new_text
                    )
            except Exception as exc:
                self.ctx._set_status(f"Fill failed: {exc}", 3)
                return

            try:
                self._push_undo()
                for cc in range(c0, c1 + 1):
                    coerced = coerced_per_col[cc]
                    for rr in range(r0, r1 + 1):
                        self.ctx.state.df.iloc[rr, cc] = coerced
                self.ctx.grid.df = self.ctx.state.df
                self.ctx.paginator.update_total_rows(len(self.ctx.state.df))
                self.ctx.paginator.ensure_row_visible(r0)
                self._set_last_action("visual_fill", value=new_text)
                self.ctx.pending_count = None
                self.ctx._set_status(f"Filled {(r1 - r0 + 1) * (c1 - c0 + 1)} cells", 2)
            except Exception as exc:
                self.ctx._set_status(f"Fill failed: {exc}", 3)
            finally:
                # exit visual mode if present
                if hasattr(self.ctx, "visual_active"):
                    self.ctx.visual_active = False
                if hasattr(self.ctx, "visual_anchor"):
                    self.ctx.visual_anchor = None
                if hasattr(self.ctx.grid, "visual_active"):
                    self.ctx.grid.visual_active = False
                if hasattr(self.ctx.grid, "visual_rect"):
                    self.ctx.grid.visual_rect = None
                self.counts.reset()
            return

        # -------- cell edit flow (existing) --------
        r = snap.get("row", self.ctx.grid.curr_row)
        c = snap.get("col", self.ctx.grid.curr_col)
        cols = self.ctx.state.df.columns
        col_name = snap.get("col_name") or (cols[c] if len(cols) else "")

        tmp_path, base = self._prepare_temp_file(r, c)
        if tmp_path is None:
            self.ctx._set_status("Open external editor failed", 3)
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

        if not col_name:
            if len(self.ctx.state.df.columns) == 0:
                self.ctx._set_status("No columns to update", 3)
                return
            c = max(0, min(c, len(self.ctx.state.df.columns) - 1))
            col_name = str(self.ctx.state.df.columns[c])

        if rc not in (0, None):
            self.ctx._set_status("Edit canceled", 3)
            return

        new_text = self._trim_editor_text(new_text)
        if new_text == base:
            self.ctx._set_status("No changes", 2)
            self.counts.reset()
            return

        try:
            self._push_undo()
            coerced = coerce_cell_value(self.ctx.state.df, col_name, new_text)
            self.ctx.state.df.iloc[r, c] = coerced
            self.ctx.grid.df = self.ctx.state.df
            self.ctx.paginator.update_total_rows(len(self.ctx.state.df))
            self.ctx.paginator.ensure_row_visible(r)
            self._set_last_action("cell_set", value=coerced)
            self.ctx.pending_count = None
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
        argv: list[str] = ["vim"]
        if read_only:
            argv += [
                "-n",
                "-R",
                "-M",
                "+setlocal nobuflisted noswapfile buftype=nofile bufhidden=wipe nowrap readonly nomodifiable nonumber norelativenumber shortmess+=I",
            ]
        return argv + [tmp_path]

    def _run_editor(self, argv: list[str]) -> int:
        runner = getattr(self.ctx, "run_interactive", None)
        if not callable(runner):
            self.ctx._set_status("External editor unavailable", 3)
            return 1
        try:
            result = runner(argv)
        except Exception:
            return 1
        if isinstance(result, int):
            return result
        if result is None:
            return 0
        if isinstance(result, (float, str)):
            try:
                return int(result)
            except Exception:
                return 1
        return 1

    def _default_config_contents(self) -> str:
        return (
            '{\n'
            '  "clipboard_interface_command": null\n'
            '}\n'
        )
