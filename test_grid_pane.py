import unittest
import pandas as pd

from grid_pane import GridPane


class DummyWin:
    def __init__(self, h=24, w=120):
        self._h = h
        self._w = w

    def getmaxyx(self):
        return self._h, self._w


def _visible_count(grid: GridPane, win: DummyWin, offset: int | None = None) -> int:
    """Replicate adjust_col_viewport's width math using header widths only."""
    _, w = win.getmaxyx()
    row_w = max(3, len(str(len(grid.df))) + 1)
    avail_w = max(20, w - (row_w + 1))

    header_widths = [min(grid.MAX_COL_WIDTH, len(str(col)) + 2) for col in grid.df.columns]

    visible_count = 0
    used = 0
    col_offset = grid.col_offset if offset is None else offset
    for cw in header_widths[col_offset:]:
        if used + cw + 1 > avail_w:
            break
        used += cw + 1
        visible_count += 1

    return max(1, visible_count)


class GridPaneAdjustViewportTests(unittest.TestCase):
    def test_adjust_col_viewport_avoids_full_df_width_scans(self):
        df = pd.DataFrame({f"c{i}": [0] for i in range(50)})
        grid = GridPane(df)
        win = DummyWin(24, 120)

        def fail_on_width(col_idx):
            raise AssertionError("get_col_width should not be called during adjust_col_viewport")

        grid.get_col_width = fail_on_width
        grid.curr_col = len(df.columns) - 1

        # Should not raise by calling get_col_width
        grid.adjust_col_viewport(win)

    def test_adjust_col_viewport_shifts_offset_using_header_estimates(self):
        df = pd.DataFrame({f"c{i}": [0] for i in range(50)})
        grid = GridPane(df)
        win = DummyWin(24, 80)

        grid.curr_col = len(df.columns) - 1

        # Expected behavior mirrors adjust_col_viewport's math: compute visible_count at
        # the current offset (0), then shift so curr_col is within that estimated window.
        initial_visible = _visible_count(grid, win, offset=grid.col_offset)
        expected_offset = grid.col_offset
        if grid.curr_col < grid.col_offset:
            expected_offset = grid.curr_col
        elif grid.curr_col >= grid.col_offset + initial_visible:
            expected_offset = grid.curr_col - initial_visible + 1

        expected_offset = max(0, expected_offset)
        max_possible_offset = max(0, len(df.columns) - initial_visible)
        expected_offset = min(expected_offset, max_possible_offset)

        grid.adjust_col_viewport(win)

        self.assertEqual(grid.col_offset, expected_offset)
        self.assertGreaterEqual(grid.col_offset, 0)
        self.assertLessEqual(grid.col_offset, grid.curr_col)


if __name__ == "__main__":
    unittest.main()
