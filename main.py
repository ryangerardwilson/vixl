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
    df = handler.load_or_create()
    state = AppState(df, path, handler)
    curses.wrapper(lambda stdscr: Orchestrator(stdscr, state).run())


if __name__ == '__main__':
    main()