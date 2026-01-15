class DfEditorVisual:
    """Visual-mode helpers for df editor."""

    def __init__(self, ctx, grid):
        self.ctx = ctx
        self.grid = grid

    def toggle(self):
        if getattr(self.ctx, "visual_active", False):
            self.exit()
        else:
            self.ctx.visual_active = True
            self.ctx.visual_anchor = (self.grid.curr_row, self.grid.curr_col)
            self._sync()

    def exit(self):
        if hasattr(self.ctx, "visual_active"):
            self.ctx.visual_active = False
        if hasattr(self.ctx, "visual_anchor"):
            self.ctx.visual_anchor = None
        if hasattr(self.grid, "visual_active"):
            self.grid.visual_active = False
        if hasattr(self.grid, "visual_rect"):
            self.grid.visual_rect = None

    def _rect(self):
        if not getattr(self.ctx, "visual_active", False):
            return None
        if not self.ctx.visual_anchor:
            return None
        ar, ac = self.ctx.visual_anchor
        cr, cc = self.grid.curr_row, self.grid.curr_col
        r0, r1 = sorted((ar, cr))
        c0, c1 = sorted((ac, cc))
        return (r0, r1, c0, c1)

    def _sync(self):
        rect = self._rect()
        if hasattr(self.grid, "visual_active"):
            self.grid.visual_active = getattr(self.ctx, "visual_active", False)
        if hasattr(self.grid, "visual_rect"):
            self.grid.visual_rect = rect

    def post_move(self):
        if getattr(self.ctx, "visual_active", False):
            self._sync()

    def clear_and_exit(self):
        self.exit()

    def rect(self):
        return self._rect()
