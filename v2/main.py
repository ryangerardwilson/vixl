import sys
import curses
import pandas as pd
from orchestrator import Orchestrator
from app_state import AppState


def main():
    if len(sys.argv) != 2:
        print("Usage: python main.py <csv>")
        sys.exit(1)
    df = pd.read_csv(sys.argv[1])
    state = AppState(df)
    curses.wrapper(lambda stdscr: Orchestrator(stdscr, state).run())


if __name__ == '__main__':
    main()