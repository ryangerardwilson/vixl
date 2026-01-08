import os
import pandas as pd


class GridModel:
    """
    Owns DataFrame loading and structural initialization.
    No rendering or input logic.
    """

    def __init__(self, state):
        self.state = state

    def load(self, file_path):
        if os.path.exists(file_path):
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            elif file_path.endswith('.parquet'):
                df = pd.read_parquet(file_path)
            else:
                raise ValueError("Unsupported file type")
        else:
            df = pd.DataFrame()
            if file_path.endswith('.csv'):
                df.to_csv(file_path, index=False)
            elif file_path.endswith('.parquet'):
                df.to_parquet(file_path)
            else:
                raise ValueError("Unsupported file type")

        # Keep native dtypes; NaN should remain NaN
        state = self.state
        state.df = df
        state.rows, state.cols = df.shape
        state.col_names = df.columns.tolist()
        state.index_name = df.index.name or ''
        state.index_values = [str(i) for i in df.index]

        state.index_width = (
            max(len(state.index_name), max(len(i) for i in state.index_values)) + 2
            if state.rows > 0 else 4
        )

        state.widths = []
        for c in range(state.cols):
            def cell_len(r):
                val = df.iloc[r, c]
                return 0 if pd.isna(val) else len(str(val))

            max_w = max(
                len(state.col_names[c]),
                max(cell_len(r) for r in range(state.rows)) if state.rows > 0 else 0
            ) + 2
            state.widths.append(max_w)

        state.file_path = file_path

    def save(self):
        """Persist df to original file path."""
        path = self.state.file_path
        df = self.state.df
        if not path:
            raise ValueError("No file path to save")
        if path.endswith('.csv'):
            df.to_csv(path, index=False)
        elif path.endswith('.parquet'):
            df.to_parquet(path)
        else:
            raise ValueError("Unsupported file type")

    def refresh_from_df(self):
        """Recompute derived state after df mutation."""
        df = self.state.df
        state = self.state
        state.rows, state.cols = df.shape
        state.col_names = df.columns.tolist()
        state.index_values = [str(i) for i in df.index]

        state.index_width = (
            max(len(state.index_name), max(len(i) for i in state.index_values)) + 2
            if state.rows > 0 else 4
        )

        state.widths = []
        for c in range(state.cols):
            def cell_len(r):
                val = df.iloc[r, c]
                return 0 if val is None or (hasattr(val, '__float__') and val != val) else len(str(val))

            max_w = max(
                len(state.col_names[c]),
                max(cell_len(r) for r in range(state.rows)) if state.rows > 0 else 0
            ) + 2
            state.widths.append(max_w)
