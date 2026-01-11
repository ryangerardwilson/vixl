import os
import sys
from pathlib import Path


class CompletionHandler:
    CONFIG_DIR = Path.home() / ".config" / "vixl"
    COMPLETIONS_DIR = CONFIG_DIR / "completions"
    BASH_COMPLETION_FILE = COMPLETIONS_DIR / "vixl.bash"
    BASH_MARKER_ENV = "VIXL_BASH_COMPLETION_ACTIVE"
    BASHRC_MARKER_BEGIN = "# >>> vixl bash completion >>>"
    BASHRC_MARKER_END = "# <<< vixl bash completion <<<"

    def __init__(self) -> None:
        pass

    def ensure_ready(self) -> None:
        self._ensure_dirs()
        if self._completion_file_needs_update():
            self._write_bash_completion_script()

        rc_path = self._rc_path()
        rc_has_block = self._rc_has_marker(rc_path)
        env_has_marker = os.environ.get(self.BASH_MARKER_ENV) == "1"

        if rc_has_block and env_has_marker:
            return

        self._print_completion_instructions(rc_path)
        sys.exit(1)

    # --- internals ---

    def _ensure_dirs(self) -> None:
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.COMPLETIONS_DIR.mkdir(parents=True, exist_ok=True)

    def _write_bash_completion_script(self) -> None:
        script = """# Vixl bash completion (HIDE_DOTFILES HIDE_PYCACHE)
if [[ -z "${VIXL_BASH_COMPLETION_ACTIVE:-}" ]]; then
    export VIXL_BASH_COMPLETION_ACTIVE=1
fi

_vixl_files() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local cmd="${COMP_WORDS[0]##*/}"
    local hide_dotfiles=1
    [[ "$cur" == .* ]] && hide_dotfiles=0

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
        local f_base="${f##*/}"
        # Skip dotfiles/dirs unless the user typed a leading '.'
        if (( hide_dotfiles )) && [[ "$f_base" == .* ]]; then
            continue
        fi
        # Skip __pycache__ unless explicitly typed
        if [[ "$f_base" == "__pycache__" && "$cur" != __pycache__* ]]; then
            continue
        fi
        if [[ -d "$f" || "$f" == *.csv || "$f" == *.parquet ]]; then
            COMPREPLY+=("$f")
        fi
    done < <(compgen -f -- "$cur")
    return 0
}

complete -o filenames -F _vixl_files python
complete -o filenames -F _vixl_files python3
complete -o filenames -F _vixl_files main.py
complete -o filenames -F _vixl_files vixl
"""
        self.BASH_COMPLETION_FILE.write_text(script)
        self.BASH_COMPLETION_FILE.chmod(0o644)

    def _completion_file_needs_update(self) -> bool:
        if not self.BASH_COMPLETION_FILE.exists():
            return True
        try:
            text = self.BASH_COMPLETION_FILE.read_text()
        except OSError:
            return True
        return (
            "complete -o filenames -F _vixl_files vixl" not in text
            or "HIDE_DOTFILES" not in text
            or "HIDE_PYCACHE" not in text
        )

    def _rc_path(self) -> Path:
        bashrc = Path.home() / ".bashrc"
        if bashrc.exists():
            return bashrc
        bash_profile = Path.home() / ".bash_profile"
        return bash_profile if bash_profile.exists() else bashrc

    def _rc_has_marker(self, rc_path: Path) -> bool:
        if not rc_path.exists():
            return False
        try:
            text = rc_path.read_text()
        except OSError:
            return False
        return self.BASHRC_MARKER_BEGIN in text and self.BASHRC_MARKER_END in text

    def _print_completion_instructions(self, rc_path: Path) -> None:
        block = (
            f"{self.BASHRC_MARKER_BEGIN}\n"
            'if [ -f "$HOME/.config/vixl/completions/vixl.bash" ]; then\n'
            '    source "$HOME/.config/vixl/completions/vixl.bash"\n'
            "fi\n"
            f"{self.BASHRC_MARKER_END}\n"
        )
        message = (
            "Vixl bash completion is not active; startup is blocked.\n\n"
            "Do this once:\n"
            f"1) Add this block to {rc_path}:\n{block}\n"
            f"2) Reload your shell or run: source {rc_path}\n"
            "3) Re-run: python main.py <csv-or-parquet> (or vixl <csv-or-parquet>)\n"
            "4) (Optional) Create a symlink in your PATH for 'vixl', e.g.:\n"
            '   ln -s "$PWD/main.py" "$HOME/.local/bin/vixl"\n'
        )
        print(message)
