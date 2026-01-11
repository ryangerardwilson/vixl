import sys
import os
import curses
from pathlib import Path
import pandas as pd
from file_type_handler import FileTypeHandler

# Make ESC snappy
os.environ.setdefault('ESCDELAY', '25')
from orchestrator import Orchestrator
from app_state import AppState


# Bash completion bootstrap
CONFIG_DIR = Path.home() / ".config" / "vixl"
COMPLETIONS_DIR = CONFIG_DIR / "completions"
BASH_COMPLETION_FILE = COMPLETIONS_DIR / "vixl.bash"
BASH_MARKER_ENV = "VIXL_BASH_COMPLETION_ACTIVE"
BASHRC_MARKER_BEGIN = "# >>> vixl bash completion >>>"
BASHRC_MARKER_END = "# <<< vixl bash completion <<<"


def _write_bash_completion_script():
    script = """# Vixl bash completion
if [[ -z "${VIXL_BASH_COMPLETION_ACTIVE:-}" ]]; then
    export VIXL_BASH_COMPLETION_ACTIVE=1
fi

_vixl_files() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local cmd="${COMP_WORDS[0]##*/}"

    if [[ "$cmd" == "python" || "$cmd" == "python3" ]]; then
        [[ ${#COMP_WORDS[@]} -ge 2 && "${COMP_WORDS[1]}" == "main.py" ]] || return 0
        [[ $COMP_CWORD -eq 2 ]] || return 0
    elif [[ "$cmd" == "main.py" || "$cmd" == "vixl" ]]; then
        [[ $COMP_CWORD -eq 1 ]] || return 0
    else
        return 0
    fi

    COMPREPLY=()
    while IFS= read -r f; do
        COMPREPLY+=("$f")
    done < <(compgen -f -- "$cur" | while read -r f; do
        if [[ -d "$f" || "$f" == *.csv || "$f" == *.parquet ]]; then
            printf '%s\n' "$f"
        fi
    done)
    return 0
}

complete -o filenames -F _vixl_files python
complete -o filenames -F _vixl_files python3
complete -o filenames -F _vixl_files main.py
complete -o filenames -F _vixl_files vixl
"""
    BASH_COMPLETION_FILE.write_text(script)
    BASH_COMPLETION_FILE.chmod(0o644)


def _completion_file_needs_update() -> bool:
    if not BASH_COMPLETION_FILE.exists():
        return True
    try:
        text = BASH_COMPLETION_FILE.read_text()
    except OSError:
        return True
    return "complete -o filenames -F _vixl_files vixl" not in text


def _rc_path():
    bashrc = Path.home() / ".bashrc"
    if bashrc.exists():
        return bashrc
    bash_profile = Path.home() / ".bash_profile"
    return bash_profile if bash_profile.exists() else bashrc


def _rc_has_marker(rc_path: Path) -> bool:
    if not rc_path.exists():
        return False
    try:
        text = rc_path.read_text()
    except OSError:
        return False
    return BASHRC_MARKER_BEGIN in text and BASHRC_MARKER_END in text


def _print_completion_instructions(rc_path: Path):
    block = (
        f"{BASHRC_MARKER_BEGIN}\n"
        "if [ -f \"$HOME/.config/vixl/completions/vixl.bash\" ]; then\n"
        "    source \"$HOME/.config/vixl/completions/vixl.bash\"\n"
        "fi\n"
        f"{BASHRC_MARKER_END}\n"
    )
    message = (
        "Vixl bash completion is not active; startup is blocked.\n\n"
        "Do this once:\n"
        f"1) Add this block to {rc_path}:\n{block}\n"
        f"2) Reload your shell or run: source {rc_path}\n"
        "3) Re-run: python main.py <csv-or-parquet>\n"
    )
    print(message)


def _ensure_bash_completion_ready():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    COMPLETIONS_DIR.mkdir(parents=True, exist_ok=True)

    if _completion_file_needs_update():
        _write_bash_completion_script()

    rc_path = _rc_path()
    rc_has_block = _rc_has_marker(rc_path)
    env_has_marker = os.environ.get(BASH_MARKER_ENV) == "1"

    if rc_has_block and env_has_marker:
        return

    _print_completion_instructions(rc_path)
    sys.exit(1)


def _default_df():
    cols = ['col_a', 'col_b', 'col_c']
    df = pd.DataFrame({c: [] for c in cols})
    for _ in range(3):
        df.loc[len(df)] = [pd.NA] * len(cols)
    return df


def main():
    _ensure_bash_completion_ready()

    has_path = len(sys.argv) == 2
    path = sys.argv[1] if has_path else None
    handler = FileTypeHandler(path) if path else None

    from loading_screen import LoadingScreen, LoadState

    load_state = LoadState()

    def load_df():
        if handler:
            return handler.load_or_create()
        return _default_df()

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
