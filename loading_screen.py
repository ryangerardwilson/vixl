# ~/Apps/vixl/loading_screen.py
import curses
import threading
import time
import random
from ascii_art import AsciiArt


class LoadState:
    def __init__(self):
        self.loaded = False
        self.aborted = False
        self.df = None


class _Stream:
    def __init__(self, x, height, rng):
        self.x = x
        self.height = height
        self.head_y = rng.uniform(0, height)
        self.speed = rng.uniform(20.0, 45.0)
        self.last = time.time()
        self.glyph_idx = rng.randint(0, 5)

    def advance(self, now):
        dt = now - self.last
        self.last = now
        self.head_y += self.speed * dt
        if self.head_y >= self.height:
            self.head_y = 0
        self.glyph_idx = (self.glyph_idx + 1) % 6


class LoadingScreen:
    PHASE_RAIN = 0
    PHASE_INTERFERE = 1
    PHASE_TAKEOVER = 2
    PHASE_FREEZE = 3
    PHASE_HOLD = 4

    GLYPHS = ["0", "1", "A", "F", "░", "▒"]

    def __init__(self, stdscr, loader_fn, load_state: LoadState):
        self.stdscr = stdscr
        self.loader_fn = loader_fn
        self.state = load_state
        self.phase = self.PHASE_RAIN
        self.phase_start = time.time()
        self.logo_fully_revealed_time = None
        self.min_logo_duration = 1.0

        self.rng = random.Random(1337)
        h, w = self.stdscr.getmaxyx()
        self.h = h
        self.w = w
        self.streams = [_Stream(x, h, self.rng) for x in range(w)]

        # logo mask
        art = AsciiArt.ART.strip("\n").splitlines()
        art_h = len(art)
        art_w = max(len(l) for l in art) if art else 0
        top = max(0, (h // 2 - art_h) // 2)
        left = max(0, (w - art_w) // 2)
        self.logo_mask = {}
        for iy, line in enumerate(art):
            for ix, ch in enumerate(line):
                if ch != " ":
                    self.logo_mask[(top + iy, left + ix)] = ch
        self.logo_cols = sorted({x for (_, x) in self.logo_mask})
        self.takeover_idx = 0

    def start_loader(self):
        t = threading.Thread(target=self._load, daemon=True)
        t.start()

    def _load(self):
        if self.state.aborted:
            return
        df = self.loader_fn()
        if not self.state.aborted:
            self.state.df = df
            self.state.loaded = True

    def run(self):
        curses.curs_set(0)
        self.stdscr.nodelay(True)
        self.start_loader()
        while not self.state.aborted:
            self.draw()
            ch = self.stdscr.getch()
            if ch == 24:  # Ctrl+X
                self.state.aborted = True
                break
            now = time.time()
            if self.phase == self.PHASE_HOLD and self.state.loaded:
                t0 = self.logo_fully_revealed_time
                if t0 is not None and now - t0 >= self.min_logo_duration:
                    break
            time.sleep(0.03)

    def draw(self):
        now = time.time()
        self.stdscr.erase()

        # Phase transitions
        elapsed = now - self.phase_start

        if (
            self.phase == self.PHASE_RAIN and elapsed > 0.3
        ):  # Reduced by ~30% from 0.8s → 0.56s
            self.phase = self.PHASE_INTERFERE
            self.phase_start = now

        elif (
            self.phase == self.PHASE_INTERFERE and elapsed > 0.2
        ):  # Still 0.4s subtle interference
            self.phase = self.PHASE_TAKEOVER
            self.phase_start = now
            self.takeover_idx = 0

        elif self.phase == self.PHASE_TAKEOVER:
            # Fast takeover: multiple columns per frame
            cols_per_frame = (
                10  # Keeps takeover very quick (~0.2–0.4s even for wide logos)
            )

            target_idx = self.takeover_idx + cols_per_frame
            while (
                self.takeover_idx < len(self.logo_cols)
                and self.takeover_idx < target_idx
            ):
                col = self.logo_cols[self.takeover_idx]
                for (y, x), ch in self.logo_mask.items():
                    if x == col:
                        try:
                            self.stdscr.addch(y, x, ch)
                        except curses.error:
                            pass
                self.takeover_idx += 1

            if self.takeover_idx >= len(self.logo_cols):
                self.phase = self.PHASE_FREEZE
                self.phase_start = now

        elif self.phase == self.PHASE_FREEZE and elapsed > 0.2:  # Quick freeze
            self.phase = self.PHASE_HOLD
            self.logo_fully_revealed_time = now
            self.phase_start = now

        # Draw matrix rain
        for s in self.streams:
            s.advance(now)
            y = int(s.head_y)
            ch = self.GLYPHS[s.glyph_idx]
            if self.phase >= self.PHASE_INTERFERE and (y, s.x) in self.logo_mask:
                continue  # Suppress rain inside logo area during/after interference
            if 0 <= y < self.h and 0 <= s.x < self.w:
                try:
                    self.stdscr.addch(y, s.x, ch)
                except curses.error:
                    pass

        # Draw full logo in freeze/hold phases
        if self.phase in (self.PHASE_FREEZE, self.PHASE_HOLD):
            for (y, x), ch in self.logo_mask.items():
                try:
                    self.stdscr.addch(y, x, ch)
                except curses.error:
                    pass

        self.stdscr.refresh()
