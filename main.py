import sys
import os
import curses
import subprocess
import json
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

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
LATEST_RELEASE_API = (
    "https://api.github.com/repos/ryangerardwilson/vixl/releases/latest"
)


def _version_tuple(version: str) -> tuple[int, ...]:
    if not version:
        return (0,)
    version = version.strip()
    if version.startswith("v"):
        version = version[1:]
    parts: list[int] = []
    for segment in version.split("."):
        digits = ""
        for ch in segment:
            if ch.isdigit():
                digits += ch
            else:
                break
        if digits == "":
            break
        parts.append(int(digits))
    return tuple(parts) if parts else (0,)


def _is_version_newer(candidate: str, current: str) -> bool:
    cand_tuple = _version_tuple(candidate)
    curr_tuple = _version_tuple(current)
    # pad tuples to same length for comparison
    length = max(len(cand_tuple), len(curr_tuple))
    cand_tuple += (0,) * (length - len(cand_tuple))
    curr_tuple += (0,) * (length - len(curr_tuple))
    return cand_tuple > curr_tuple


def _get_latest_version(timeout: float = 5.0) -> str | None:
    try:
        request = Request(LATEST_RELEASE_API, headers={"User-Agent": "vixl-updater"})
        with urlopen(request, timeout=timeout) as resp:
            data = resp.read().decode("utf-8", errors="replace")
    except (URLError, HTTPError, TimeoutError):
        return None
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return None
    tag = payload.get("tag_name") or payload.get("name")
    if isinstance(tag, str) and tag.strip():
        return tag.strip()
    return None


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
        latest = _get_latest_version()
        if latest is None:
            print(
                "Unable to determine latest version; attempting upgrade…",
                file=sys.stderr,
            )
            rc = _run_upgrade()
            sys.exit(rc)

        if (
            __version__
            and __version__ != "0.0.0"
            and not _is_version_newer(latest, __version__)
        ):
            print(f"Already running the latest version ({__version__}).")
            sys.exit(0)

        if __version__ and __version__ != "0.0.0":
            print(f"Upgrading from {__version__} to {latest}…")
        else:
            print(f"Upgrading to {latest}…")
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
            if load_state.error:
                print(f"Load failed: {load_state.error}", file=sys.stderr)
            return
        state = AppState(load_state.df, path, handler)
        Orchestrator(stdscr, state).run()

    curses.wrapper(curses_main)


if __name__ == "__main__":
    main()
