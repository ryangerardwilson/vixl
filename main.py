import sys
import os
import curses
from file_type_handler import FileTypeHandler
from completions_handler import CompletionHandler
from default_df_initializer import DefaultDfInitializer

# Make ESC snappy
os.environ.setdefault("ESCDELAY", "25")
from orchestrator import Orchestrator
from app_state import AppState

try:
    from _version import __version__
except Exception:
    __version__ = "0.0.0"


def main():
    args = sys.argv[1:]

    if "--version" in args or "-V" in args:
        print(__version__)
        return

    if "--help" in args or "-h" in args:
        print(
            "vixl - terminal-native spreadsheet editor\n\nUsage:\n  vixl [path]\n  vixl --version\n"
        )
        return

    CompletionHandler().ensure_ready()

    has_path = len(args) == 1
    path = args[0] if has_path else None
    handler = FileTypeHandler(path) if path else None

    from loading_screen import LoadingScreen, LoadState

    load_state = LoadState()

    def load_df():
        if handler:
            return handler.load_or_create()
        return DefaultDfInitializer().create()

    def curses_main(stdscr):
        loader = LoadingScreen(stdscr, load_df, load_state)
        loader.run()
        if load_state.aborted:
            return
        state = AppState(load_state.df, path, handler)
        Orchestrator(stdscr, state).run()

    curses.wrapper(curses_main)


if __name__ == "__main__":
    main()
