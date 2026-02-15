import os
import sys
import pandas as pd

from default_df_initializer import DefaultDfInitializer


class FileTypeHandler:
    DEFAULT_SHEET_NAME = "Sheet1"

    def __init__(self, path: str):
        self.path = path
        _, ext = os.path.splitext(path)
        self.ext = ext.lower()

        if self.ext not in {".csv", ".parquet", ".xlsx", ".h5"}:
            print("Unsupported file type (use .csv, .parquet, .xlsx, or .h5)")
            sys.exit(1)

    def load_or_create(self) -> pd.DataFrame | dict[str, pd.DataFrame]:
        if not os.path.exists(self.path) or os.path.getsize(self.path) == 0:
            return self._default_payload()

        if self.ext == ".csv":
            try:
                df = pd.read_csv(self.path)
            except pd.errors.EmptyDataError:
                return self._default_payload()
            return self._ensure_non_empty(df)
        elif self.ext == ".parquet":
            self._ensure_parquet_engine()
            try:
                df = pd.read_parquet(self.path)
            except Exception as exc:
                try:
                    import pyarrow

                    if isinstance(exc, pyarrow.ArrowInvalid):
                        return self._default_payload()
                except Exception:
                    pass
                raise
            return self._ensure_non_empty(df)
        elif self.ext == ".xlsx":
            return self._load_excel()
        elif self.ext == ".h5":
            return self._load_hdf()

        print("Unsupported file type (use .csv, .parquet, .xlsx, or .h5)")
        sys.exit(1)

    def save(self, df: pd.DataFrame | dict[str, pd.DataFrame]) -> None:
        self._write(df)

    def _write(self, df: pd.DataFrame | dict[str, pd.DataFrame]) -> None:
        if self.ext == ".csv":
            if isinstance(df, dict):
                df = next(iter(df.values()), self._default_df())
            df.to_csv(self.path, index=False)
        elif self.ext == ".parquet":
            self._ensure_parquet_engine()
            if isinstance(df, dict):
                df = next(iter(df.values()), self._default_df())
            df.to_parquet(self.path)
        elif self.ext == ".xlsx":
            self._ensure_excel_engine()
            self._write_excel(df)
        elif self.ext == ".h5":
            self._ensure_hdf_engine()
            self._write_hdf(df)
        else:
            print("Unsupported file type (use .csv, .parquet, .xlsx, or .h5)")
            sys.exit(1)

    def _ensure_non_empty(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty or df.shape[1] == 0:
            return self._default_df()
        return df

    def _default_df(self) -> pd.DataFrame:
        return DefaultDfInitializer().create()

    def _default_payload(self) -> pd.DataFrame | dict[str, pd.DataFrame]:
        df = self._default_df()
        if self.ext in {".xlsx", ".h5"}:
            return self._default_sheet_dict(df)
        return df

    def _default_sheet_dict(self, df: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
        base = df if isinstance(df, pd.DataFrame) else self._default_df()
        return {self.DEFAULT_SHEET_NAME: base}

    def _load_excel(self) -> dict[str, pd.DataFrame]:
        self._ensure_excel_engine()
        try:
            sheets = pd.read_excel(self.path, sheet_name=None)
        except Exception:
            return self._default_sheet_dict()
        if not sheets:
            return self._default_sheet_dict()
        cleaned = {}
        for name, df in sheets.items():
            if not isinstance(df, pd.DataFrame):
                continue
            cleaned[name] = self._ensure_non_empty(df)
        return cleaned if cleaned else self._default_sheet_dict()

    def _load_hdf(self) -> dict[str, pd.DataFrame]:
        self._ensure_hdf_engine()
        try:
            with pd.HDFStore(self.path, mode="r") as store:
                keys = store.keys()
                sheets = {}
                for key in keys:
                    try:
                        obj = store.get(key)
                    except Exception:
                        continue
                    if isinstance(obj, pd.DataFrame):
                        name = key.lstrip("/") or self.DEFAULT_SHEET_NAME
                        sheets[name] = self._ensure_non_empty(obj)
        except Exception:
            return self._default_sheet_dict()
        return sheets if sheets else self._default_sheet_dict()

    def _ensure_parquet_engine(self):
        try:
            import pyarrow  # noqa: F401

            return
        except ImportError:
            pass
        print("Parquet support requires pyarrow. Install via: pip install pyarrow")
        sys.exit(1)

    def _ensure_excel_engine(self):
        try:
            import openpyxl  # noqa: F401

            return
        except ImportError:
            pass
        print("XLSX support requires openpyxl. Install via: pip install openpyxl")
        sys.exit(1)

    def _ensure_hdf_engine(self):
        try:
            import tables  # type: ignore  # noqa: F401

            return
        except ImportError:
            pass
        print("HDF5 support requires tables. Install via: pip install tables")
        sys.exit(1)

    def _write_excel(self, df: pd.DataFrame | dict[str, pd.DataFrame]):
        sheets = df if isinstance(df, dict) else None
        if not sheets:
            sheets = {self.DEFAULT_SHEET_NAME: df}
        with pd.ExcelWriter(self.path) as writer:
            for name, sheet_df in sheets.items():
                if not isinstance(sheet_df, pd.DataFrame):
                    continue
                sheet_df.to_excel(writer, index=False, sheet_name=name)

    def _write_hdf(self, df: pd.DataFrame | dict[str, pd.DataFrame]):
        sheets = df if isinstance(df, dict) else None
        if not sheets:
            sheets = {self.DEFAULT_SHEET_NAME: df}
        with pd.HDFStore(self.path, mode="w") as store:
            for name, sheet_df in sheets.items():
                if not isinstance(sheet_df, pd.DataFrame):
                    continue
                store.put(name, sheet_df)
