class AppState:
    def __init__(self, df, file_path):
        self.df = df
        self.file_path = file_path

    def save(self):
        if not self.file_path:
            return
        if self.file_path.endswith('.csv'):
            self.df.to_csv(self.file_path, index=False)
        elif self.file_path.endswith('.parquet'):
            self.df.to_parquet(self.file_path)
        else:
            raise ValueError("Unsupported file type")