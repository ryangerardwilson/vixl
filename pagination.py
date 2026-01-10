class Paginator:
    def __init__(self, total_rows: int, page_size: int = 1000):
        self.page_size = page_size
        self.page_index = 0
        self.total_rows = max(0, total_rows)
        self._clamp()

    def _clamp(self):
        max_page = self.page_count - 1
        self.page_index = max(0, min(self.page_index, max_page))

    def update_total_rows(self, total_rows: int):
        self.total_rows = max(0, total_rows)
        self._clamp()

    def next_page(self):
        if self.page_end < self.total_rows:
            self.page_index += 1
            self._clamp()

    def prev_page(self):
        if self.page_index > 0:
            self.page_index -= 1
            self._clamp()

    def ensure_row_visible(self, row: int):
        if row < 0:
            row = 0
        if self.total_rows == 0:
            self.page_index = 0
            return
        target_index = row // self.page_size
        if target_index != self.page_index:
            self.page_index = target_index
            self._clamp()

    @property
    def page_start(self) -> int:
        return self.page_index * self.page_size

    @property
    def page_end(self) -> int:
        return min(self.total_rows, self.page_start + self.page_size)

    @property
    def page_count(self) -> int:
        if self.total_rows == 0:
            return 1
        return (self.total_rows - 1) // self.page_size + 1
