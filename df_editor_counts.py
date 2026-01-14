class DfEditorCounts:
    """Handles numeric prefix (count) tracking for DfEditor."""

    def __init__(self, ctx):
        self.ctx = ctx

    def reset(self):
        self.ctx.pending_count = None

    def push_digit(self, digit: int):
        if digit < 0 or digit > 9:
            return
        if self.ctx.pending_count is None:
            self.ctx.pending_count = digit
        else:
            self.ctx.pending_count = min(9999, self.ctx.pending_count * 10 + digit)

    def consume(self, default: int = 1) -> int:
        count = (
            self.ctx.pending_count if self.ctx.pending_count is not None else default
        )
        self.ctx.pending_count = None
        return max(1, count)
