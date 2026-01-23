import sys
import os
import curses
import subprocess

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


INSTALL_URL = "https://raw.githubusercontent.com/ryangerardwilson/vixl/main/install.sh"


def _run_upgrade():
    try:
        curl = subprocess.Popen(
            ["curl", "-fsSL", INSTALL_URL],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        print("Upgrade requires curl", file=sys.stderr)
        return 1

    try:
        bash = subprocess.Popen(["bash"], stdin=curl.stdout)
        if curl.stdout is not None:
            curl.stdout.close()
    except FileNotFoundError:
        print("Upgrade requires bash", file=sys.stderr)
        curl.terminate()
        curl.wait()
        return 1

    bash_rc = bash.wait()
    curl_rc = curl.wait()

    if curl_rc != 0:
        stderr = (
            curl.stderr.read().decode("utf-8", errors="replace") if curl.stderr else ""
        )
        if stderr:
            sys.stderr.write(stderr)
        return curl_rc

    return bash_rc


def main():
    args = sys.argv[1:]

    if "-v" in args or "-V" in args:
        print(__version__)
        return

    if "-h" in args:
        print(
            "vixl - terminal-native spreadsheet editor\n\nUsage:\n  vixl [path]\n  vixl -v\n  vixl -u\n"
        )
        return

    if "-u" in args:
        rc = _run_upgrade()
        sys.exit(rc)

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
