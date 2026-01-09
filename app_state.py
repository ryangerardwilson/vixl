import pandas as pd
import numpy as np


class AppState:
    def __init__(self, df, file_path, file_handler):
        self.file_path = file_path
        self.file_handler = file_handler
        self.df = self._ensure_non_empty(df)

    def ensure_non_empty(self):
        self.df = self._ensure_non_empty(self.df)

    def _ensure_non_empty(self, df):
        if len(df) > 0:
            return df

        if df.columns.size == 0:
            return df

        row = {}
        for col, dtype in df.dtypes.items():
            if pd.api.types.is_datetime64_any_dtype(dtype):
                row[col] = pd.NaT
            elif pd.api.types.is_numeric_dtype(dtype):
                row[col] = np.nan
            else:
                row[col] = pd.NA

        df = df.copy()
        df.loc[0] = row
        return df