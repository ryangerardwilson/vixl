import sys
import os
import curses
from pathlib import Path

import config_paths
from file_type_handler import FileTypeHandler
from completions_handler import CompletionHandler
from default_df_initializer import DefaultDfInitializer
from rgw_cli_contract import AppSpec, resolve_install_script_path, run_app

# Make ESC snappy
os.environ.setdefault("ESCDELAY", "25")
from orchestrator import Orchestrator
from app_state import AppState

from _version import __version__


INSTALL_SCRIPT = resolve_install_script_path(__file__)
HELP_TEXT = """vixl

flags:
  vixl -h
    show this help
  vixl -v
    print the installed version
  vixl -u
    upgrade to the latest release
  vixl conf
    open the config in $VISUAL/$EDITOR

features:
  open the spreadsheet editor on a path or a new sheet
  # vixl [path]
  vixl
  vixl data.csv
"""


def _config_path() -> Path:
    return Path(config_paths.CONFIG_JSON)


def _dispatch(args: list[str]) -> int:
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
            if load_state.error:
                print(f"Load failed: {load_state.error}", file=sys.stderr)
            return
        state = AppState(load_state.df, path, handler)
        Orchestrator(stdscr, state).run()

    curses.wrapper(curses_main)
    return 0


APP_SPEC = AppSpec(
    app_name="vixl",
    version=__version__,
    help_text=HELP_TEXT,
    install_script_path=INSTALL_SCRIPT,
    no_args_mode="dispatch",
    config_path_factory=_config_path,
)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    return run_app(APP_SPEC, args, _dispatch)


if __name__ == "__main__":
    main()
