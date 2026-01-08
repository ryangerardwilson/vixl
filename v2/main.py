import sys
import curses
import pandas as pd
from orchestrator import Orchestrator
from app_state import AppState


def main():
    if len(sys.argv) != 2:
        print("Usage: python main.py <csv>")
        sys.exit(1)
    path = sys.argv[1]
    df = pd.read_csv(path)
    state = AppState(df, path)
    curses.wrapper(lambda stdscr: Orchestrator(stdscr, state).run())


if __name__ == '__main__':
    main()