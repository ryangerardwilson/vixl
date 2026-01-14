import pandas as pd


class DfEditorDfOps:
    """DataFrame-level operations invoked from DF mode and repeat actions."""

    def __init__(self, ctx, counts, undo_mgr):
        self.ctx = ctx
        self.counts = counts
        self.undo_mgr = undo_mgr

    # ----- row height / expansion -----
    def adjust_row_lines(self, delta: int, minimum: int = 1, maximum: int = 10):
        current = self.ctx.state.row_lines
        new_value = max(minimum, min(maximum, current + delta))
        if new_value == current:
            bound = "minimum" if delta < 0 else "maximum"
            self.ctx._set_status(f"Row lines {bound} reached ({new_value})", 2)
            return
        applied_delta = new_value - current
        self.ctx.state.row_lines = new_value
        self.ctx.grid.row_offset = 0
        self.ctx._set_status(f"Row lines set to {self.ctx.state.row_lines}", 2)
        self.undo_mgr.set_last_action("adjust_row_lines", delta=applied_delta)

    def toggle_row_expanded(self):
        if len(self.ctx.state.df) == 0:
            self.ctx._set_status("No rows to expand", 2)
            return
        row = max(0, min(self.ctx.grid.curr_row, len(self.ctx.state.df) - 1))
        expanded = getattr(self.ctx.state, "expanded_rows", set())
        if row in expanded:
            expanded.remove(row)
            self.ctx._set_status("Row collapsed", 2)
        else:
            expanded.add(row)
            self.ctx._set_status("Row expanded", 2)
        self.ctx.state.expand_all_rows = (
            False if not expanded else self.ctx.state.expand_all_rows
        )
        self.ctx.grid.row_offset = 0
        self.counts.reset()

    def toggle_all_rows_expanded(self):
        self.ctx.state.expand_all_rows = not getattr(
            self.ctx.state, "expand_all_rows", False
        )
        state = "expanded" if self.ctx.state.expand_all_rows else "collapsed"
        self.ctx._set_status(f"All rows {state}", 2)
        self.ctx.grid.row_offset = 0
        self.counts.reset()

    def collapse_all_rows(self):
        self.ctx.state.expand_all_rows = False
        self.ctx.state.expanded_rows = set()
        self.ctx.grid.row_offset = 0
        self.ctx._set_status("All rows collapsed", 2)
        self.counts.reset()

    # ----- column prompt helpers -----
    def start_insert_column(self, after: bool):
        if self.ctx.column_prompt is None:
            self.ctx._set_status("Column prompt unavailable", 3)
            return
        if len(self.ctx.state.df.columns) == 0:
            self.ctx._set_status("No columns", 3)
            return
        if after:
            self.ctx.column_prompt.start_insert_after(self.ctx.grid.curr_col)
        else:
            self.ctx.column_prompt.start_insert_before(self.ctx.grid.curr_col)

    def start_rename_column(self):
        if self.ctx.column_prompt is None:
            self.ctx._set_status("Column prompt unavailable", 3)
            return
        if len(self.ctx.state.df.columns) == 0:
            self.ctx._set_status("No columns", 3)
            return
        self.ctx.column_prompt.start_rename(self.ctx.grid.curr_col)

    # ----- row operations -----
    def insert_rows(self, above: bool, count: int = 1):
        if len(self.ctx.state.df.columns) == 0:
            self.ctx._set_status("No columns", 3)
            return
        count = max(1, count)
        self.undo_mgr.push_undo()
        insert_at = (
            self.ctx.grid.curr_row
            if above
            else (self.ctx.grid.curr_row + 1 if len(self.ctx.state.df) > 0 else 0)
        )
        row = self.ctx.state.build_default_row()
        new_rows = pd.DataFrame([row] * count, columns=self.ctx.state.df.columns)
        self.ctx.state.df = pd.concat(
            [
                self.ctx.state.df.iloc[:insert_at],
                new_rows,
                self.ctx.state.df.iloc[insert_at:],
            ],
            ignore_index=True,
        )
        self.ctx.grid.df = self.ctx.state.df
        self.ctx.paginator.update_total_rows(len(self.ctx.state.df))
        self.ctx.paginator.ensure_row_visible(insert_at)
        self.ctx.grid.curr_row = insert_at
        self.ctx.grid.highlight_mode = "cell"
        self.ctx._set_status(
            f"Inserted {count} row{'s' if count != 1 else ''} {'above' if above else 'below'}",
            2,
        )
        self.undo_mgr.set_last_action("insert_rows", count=count, above=above)

    def insert_row(self, above: bool):
        self.insert_rows(above=above, count=1)

    def delete_rows(self, count: int = 1):
        total_rows = len(self.ctx.state.df)
        if total_rows == 0:
            self.ctx._set_status("No rows", 3)
            return
        count = max(1, count)
        self.undo_mgr.push_undo()
        start = self.ctx.grid.curr_row
        end = min(total_rows, start + count)
        self.ctx.state.df = self.ctx.state.df.drop(
            self.ctx.state.df.index[start:end]
        ).reset_index(drop=True)
        self.ctx.grid.df = self.ctx.state.df
        total_rows = len(self.ctx.state.df)
        self.ctx.grid.curr_row = min(start, max(0, total_rows - 1))
        self.ctx.paginator.update_total_rows(total_rows)
        if total_rows:
            self.ctx.paginator.ensure_row_visible(self.ctx.grid.curr_row)
        self.ctx.grid.highlight_mode = "cell"
        deleted = end - start
        self.ctx._set_status(f"Deleted {deleted} row{'s' if deleted != 1 else ''}", 2)
        self.undo_mgr.set_last_action("delete_rows", count=deleted)

    # ----- column operations -----
    def delete_current_column(self):
        cols = list(self.ctx.state.df.columns)
        if not cols:
            self.ctx._set_status("No columns", 3)
            return
        self.undo_mgr.push_undo()
        col_idx = self.ctx.grid.curr_col
        col_name = cols[col_idx]
        self.ctx.state.df.drop(columns=[col_name], inplace=True)
        self.ctx.grid.df = self.ctx.state.df
        total_cols = len(self.ctx.state.df.columns)
        self.ctx.grid.curr_col = min(col_idx, max(0, total_cols - 1))
        self.ctx.grid.adjust_col_viewport()
        self.ctx._set_status(f"Deleted column '{col_name}'", 3)
        self.undo_mgr.set_last_action("col_delete", col_name=col_name)
