import os
import subprocess
import sys
import curses
from pathlib import Path

import config_paths
from file_type_handler import FileTypeHandler
from completions_handler import CompletionHandler
from default_df_initializer import DefaultDfInitializer

# Make ESC snappy
os.environ.setdefault("ESCDELAY", "25")
from orchestrator import Orchestrator
from app_state import AppState

from _version import __version__


HELP_TEXT = """vixl
terminal spreadsheet editor for CSV, Parquet, XLSX, and HDF5 files

flags:
  vixl -h
    show this help
  vixl -v
    print the installed version
  vixl -u
    upgrade to the latest release
  vixl config
    open the config in $VISUAL/$EDITOR

features:
  open the spreadsheet editor on a new sheet or an existing path
  # vixl open [path]
  vixl open
  vixl open data.csv

  edit command history, clipboard integration, and other local settings
  # vixl config
  vixl config
"""


def _print_help() -> None:
    print(HELP_TEXT.rstrip())


def _app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _install_script_path() -> Path:
    override = os.environ.get("VIXL_INSTALL_SCRIPT")
    if override:
        return Path(override)
    return _app_root() / "install.sh"


def _upgrade() -> int:
    return subprocess.run(
        ["/usr/bin/env", "bash", str(_install_script_path()), "-u"],
        check=False,
    ).returncode


def _open_config() -> int:
    config_paths.ensure_config_dirs()
    config_path = Path(config_paths.CONFIG_JSON)
    if not config_path.exists():
        config_path.write_text("{}\n", encoding="utf-8")
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vim"
    return subprocess.run([editor, str(config_path)], check=False).returncode


def _dispatch(args: list[str]) -> int:
    if not args or args[0] != "open" or len(args) > 2:
        print("Usage: vixl open [path]")
        return 1

    CompletionHandler().ensure_ready()

    path = args[1] if len(args) == 2 else None
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
            if load_state.error:
                print(f"Load failed: {load_state.error}", file=sys.stderr)
            return
        state = AppState(load_state.df, path, handler)
        Orchestrator(stdscr, state).run()

    curses.wrapper(curses_main)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args == ["-h"]:
        _print_help()
        return 0
    if args == ["-v"]:
        print(__version__)
        return 0
    if args == ["-u"]:
        return _upgrade()
    if args and args[0] == "config":
        if len(args) != 1:
            print("Usage: vixl config")
            return 1
        return _open_config()
    return _dispatch(args)


if __name__ == "__main__":
    main()
