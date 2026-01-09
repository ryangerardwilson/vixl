import os
import sys
import pandas as pd


class FileTypeHandler:
    def __init__(self, path: str):
        self.path = path
        _, ext = os.path.splitext(path)
        self.ext = ext.lower()

        if self.ext not in {'.csv', '.parquet'}:
            print("Unsupported file type (use .csv or .parquet)")
            sys.exit(1)

    def load_or_create(self) -> pd.DataFrame:
        if not os.path.exists(self.path):
            df = pd.DataFrame()
            self._write(df)
            return df

        if self.ext == '.csv':
            return pd.read_csv(self.path)
        elif self.ext == '.parquet':
            return pd.read_parquet(self.path)

        print("Unsupported file type (use .csv or .parquet)")
        sys.exit(1)

    def save(self, df: pd.DataFrame) -> None:
        self._write(df)

    def _write(self, df: pd.DataFrame) -> None:
        if self.ext == '.csv':
            df.to_csv(self.path, index=False)
        elif self.ext == '.parquet':
            df.to_parquet(self.path)
        else:
            print("Unsupported file type (use .csv or .parquet)")
            sys.exit(1)