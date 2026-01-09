import sys
import os
import curses
from file_type_handler import FileTypeHandler

# Make ESC snappy
os.environ.setdefault('ESCDELAY', '25')
from orchestrator import Orchestrator
from app_state import AppState


def main():
    if len(sys.argv) != 2:
        print("Usage: python main.py <csv|parquet>")
        sys.exit(1)

    path = sys.argv[1]
    handler = FileTypeHandler(path)

    from loading_screen import LoadingScreen, LoadState

    load_state = LoadState()

    def load_df():
        return handler.load_or_create()

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