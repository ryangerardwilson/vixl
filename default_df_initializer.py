import pandas as pd


class DefaultDfInitializer:
    def create(self) -> pd.DataFrame:
        cols = ["col_a", "col_b", "col_c"]
        df = pd.DataFrame({c: [] for c in cols})
        for _ in range(3):
            df.loc[len(df)] = [pd.NA] * len(cols)
        return df
