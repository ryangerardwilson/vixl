import pandas as pd
import numpy as np


class AppState:
    def __init__(self, df, file_path, file_handler):
         self.file_path = file_path
         self.file_handler = file_handler
         self.df = self._ensure_non_empty(df)
         self.row_lines = 1


    def ensure_non_empty(self):
        self.df = self._ensure_non_empty(self.df)

    def build_default_row(self, df=None):
        target = df if df is not None else self.df
        row = {}
        for col, dtype in target.dtypes.items():
            if pd.api.types.is_datetime64_any_dtype(dtype):
                row[col] = pd.NaT
            elif pd.api.types.is_numeric_dtype(dtype):
                row[col] = np.nan
            else:
                row[col] = pd.NA
        return row

    def _ensure_non_empty(self, df):
        if len(df) > 0:
            return df

        if df.columns.size == 0:
            return df

        row = self.build_default_row(df)

        df = df.copy()
        df.loc[0] = row
        return df
