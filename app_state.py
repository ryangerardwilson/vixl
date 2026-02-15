import pandas as pd
import numpy as np


class AppState:
    def __init__(self, df, file_path, file_handler, sheets=None, active_sheet=None):
        self.file_path = file_path
        self.file_handler = file_handler

        self.sheets: dict[str, pd.DataFrame] | None = None
        self.sheet_order: list[str] = []
        self.active_sheet: str | None = None

        self._df = None
        self._undo_stacks: dict[str, list] = {}
        self._redo_stacks: dict[str, list] = {}
        self.undo_max_depth = 50

        self.row_lines = 1
        self.expanded_rows: set[int] = set()
        self.expand_all_rows: bool = False

        self._init_sheets(df, sheets=sheets, active_sheet=active_sheet)

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
        if df is None:
            return pd.DataFrame()
        if len(df) > 0:
            return df

        if df.columns.size == 0:
            return df

        row = self.build_default_row(df)

        df = df.copy()
        df.loc[0] = row
        return df

    def _init_sheets(self, df, sheets=None, active_sheet=None):
        if sheets is None and isinstance(df, dict):
            sheets = df
            df = None

        if isinstance(sheets, dict) and sheets:
            cleaned = {}
            for name, value in sheets.items():
                if not isinstance(name, str):
                    name = str(name)
                if isinstance(value, pd.DataFrame):
                    cleaned[name] = value
            if cleaned:
                self.sheets = cleaned
                self.sheet_order = list(cleaned.keys())
                if active_sheet in cleaned:
                    self.active_sheet = active_sheet
                else:
                    self.active_sheet = self.sheet_order[0]
                self._df = self._ensure_non_empty(self.sheets[self.active_sheet])
                self.sheets[self.active_sheet] = self._df
                return

        self.sheets = None
        self.sheet_order = []
        self.active_sheet = None
        self._df = self._ensure_non_empty(df)

    def _sheet_key(self) -> str:
        return self.active_sheet if self.sheets else "__default__"

    @property
    def df(self):
        return self._df

    @df.setter
    def df(self, value):
        self._df = self._ensure_non_empty(value)
        if self.sheets and self.active_sheet:
            self.sheets[self.active_sheet] = self._df

    @property
    def undo_stack(self):
        key = self._sheet_key()
        if key not in self._undo_stacks:
            self._undo_stacks[key] = []
        return self._undo_stacks[key]

    @undo_stack.setter
    def undo_stack(self, value):
        key = self._sheet_key()
        self._undo_stacks[key] = list(value or [])

    @property
    def redo_stack(self):
        key = self._sheet_key()
        if key not in self._redo_stacks:
            self._redo_stacks[key] = []
        return self._redo_stacks[key]

    @redo_stack.setter
    def redo_stack(self, value):
        key = self._sheet_key()
        self._redo_stacks[key] = list(value or [])

    def has_sheets(self) -> bool:
        return bool(self.sheets)

    def get_sheet_names(self) -> list[str]:
        return list(self.sheet_order) if self.sheets else []

    def get_active_sheet_name(self) -> str | None:
        return self.active_sheet

    def set_active_sheet(self, name: str) -> bool:
        if not self.sheets or name not in self.sheets:
            return False
        self.active_sheet = name
        self._df = self._ensure_non_empty(self.sheets[name])
        self.sheets[name] = self._df
        return True

    def switch_sheet(self, delta: int) -> str | None:
        if not self.sheets or not self.sheet_order:
            return None
        if self.active_sheet not in self.sheet_order:
            self.active_sheet = self.sheet_order[0]
        idx = self.sheet_order.index(self.active_sheet)
        new_idx = (idx + delta) % len(self.sheet_order)
        new_name = self.sheet_order[new_idx]
        self.set_active_sheet(new_name)
        return new_name
