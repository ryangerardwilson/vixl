import sys
import os
import curses
import pandas as pd
from file_type_handler import FileTypeHandler

# Make ESC snappy
os.environ.setdefault('ESCDELAY', '25')
from orchestrator import Orchestrator
from app_state import AppState


def _default_df():
    cols = ['col_a', 'col_b', 'col_c']
    df = pd.DataFrame({c: [] for c in cols})
    for _ in range(3):
        df.loc[len(df)] = [pd.NA] * len(cols)
    return df


def main():
    has_path = len(sys.argv) == 2
    path = sys.argv[1] if has_path else None
    handler = FileTypeHandler(path) if path else None

    from loading_screen import LoadingScreen, LoadState

    load_state = LoadState()

    def load_df():
        if handler:
            return handler.load_or_create()
        return _default_df()

    def curses_main(stdscr):
        loader = LoadingScreen(stdscr, load_df, load_state)
        loader.run()
        if load_state.aborted:
            return
        state = AppState(load_state.df, path, handler)
        Orchestrator(stdscr, state).run()

    curses.wrapper(curses_main)


if __name__ == '__main__':
    main()
