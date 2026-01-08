#!/usr/bin/env python3

import curses
import os

os.environ.setdefault('ESCDELAY', '25')
from app_state import AppState
from orchestrator import Orchestrator


def main(stdscr):
    # Disable terminal flow control (Ctrl+S / Ctrl+Q)
    import sys, termios
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    new = list(old)
    new[0] &= ~termios.IXON
    termios.tcsetattr(fd, termios.TCSADRAIN, new)
    state = AppState()
    orchestrator = Orchestrator(stdscr, state)
    orchestrator.run()


if __name__ == "__main__":
    curses.wrapper(main)
