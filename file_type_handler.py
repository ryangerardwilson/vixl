import os
import sys
import pandas as pd

from default_df_initializer import DefaultDfInitializer


class FileTypeHandler:
    def __init__(self, path: str):
        self.path = path
        _, ext = os.path.splitext(path)
        self.ext = ext.lower()

        if self.ext not in {".csv", ".parquet"}:
            print("Unsupported file type (use .csv or .parquet)")
            sys.exit(1)

    def load_or_create(self) -> pd.DataFrame:
        if not os.path.exists(self.path) or os.path.getsize(self.path) == 0:
            return self._default_df()

        if self.ext == ".csv":
            try:
                df = pd.read_csv(self.path)
            except pd.errors.EmptyDataError:
                return self._default_df()
            return self._ensure_non_empty(df)
        elif self.ext == ".parquet":
            self._ensure_parquet_engine()
            try:
                df = pd.read_parquet(self.path)
            except Exception as exc:
                try:
                    import pyarrow

                    if isinstance(exc, pyarrow.ArrowInvalid):
                        return self._default_df()
                except Exception:
                    pass
                raise
            return self._ensure_non_empty(df)

        print("Unsupported file type (use .csv or .parquet)")
        sys.exit(1)

    def save(self, df: pd.DataFrame) -> None:
        self._write(df)

    def _write(self, df: pd.DataFrame) -> None:
        if self.ext == ".csv":
            df.to_csv(self.path, index=False)
        elif self.ext == ".parquet":
            self._ensure_parquet_engine()
            df.to_parquet(self.path)
        else:
            print("Unsupported file type (use .csv or .parquet)")
            sys.exit(1)

    def _ensure_non_empty(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty or df.shape[1] == 0:
            return self._default_df()
        return df

    def _default_df(self) -> pd.DataFrame:
        return DefaultDfInitializer().create()

    def _ensure_parquet_engine(self):
        try:
            import pyarrow  # noqa: F401

            return
        except ImportError:
            pass
        print("Parquet support requires pyarrow. Install via: pip install pyarrow")
        sys.exit(1)
