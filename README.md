# Vixl

Vixl is a **Vim-first, terminal-native spreadsheet editor** for fast, explicit
manipulation of tabular data using Pandas and NumPy.

It is designed for users who prefer keyboard-driven workflows and want full
transparency over how their data is transformed.

---

## Installation

### Prebuilt binary (Linux x86_64)

The fastest way to get Vixl is to install the prebuilt PyInstaller binary that ships with each GitHub release:

```bash
curl -fsSL https://raw.githubusercontent.com/ryangerardwilson/vixl/main/install.sh | bash
```

- Installs to `~/.vixl/bin/vixl` and adds that directory to your PATH (unless you pass `--no-modify-path`).
- The script auto-detects the latest release. Pin a specific version with `--version`, e.g. `... | bash -s -- --version 0.1.16`.
- You can install from a local artifact with `--binary /path/to/vixl`.
- Requirements: Linux x86_64 with `curl` and `tar` available.

### From source (venv)

```bash
git clone https://github.com/ryangerardwilson/vixl.git
cd vixl
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

## Running the App

- **Binary install**: run `vixl <csv-or-parquet-file>` directly (binary lives in `~/.vixl/bin`).
- **From source/venv**: activate the venv and run:

```bash
python main.py <csv-or-parquet-file>
```

- CSV is always supported; Parquet requires `pyarrow` (installed via requirements.txt).
- If the file does not exist, a blank file is created automatically

### Optional: create a `vixl` command

```bash
chmod +x main.py
ln -sf "$(pwd)/main.py" "$HOME/.local/bin/vixl"
```

Ensure `~/.local/bin` is on your PATH, and activate the venv before running `vixl`.

### Bash completion (auto-provisioned, warning-only)
- On first run, Vixl creates `$XDG_CONFIG_HOME/vixl/completions/vixl.bash` (default `~/.config/vixl/completions/vixl.bash`).
- Add this block to your `~/.bashrc` (or `~/.bash_profile` if you do not have a `.bashrc`):
  ```bash
  # >>> vixl bash completion >>>
  if [ -f "${XDG_CONFIG_HOME:-$HOME/.config}/vixl/completions/vixl.bash" ]; then
      source "${XDG_CONFIG_HOME:-$HOME/.config}/vixl/completions/vixl.bash"
  fi
  # <<< vixl bash completion <<<
  ```
- Then reload your shell (or run `source ~/.bashrc`).
- If completion is not detected, Vixl prints a warning and continues to launch. To silence the warning without enabling completion, set `VIXL_SKIP_COMPLETION_CHECK=1` in your environment.
- Behavior: after activation, **only** `vixl <TAB>` is completed; `python main.py` is intentionally not hooked to avoid interfering with ordinary Python. Completions suggest only `.csv` and `.parquet` files for the first argument; directories are still offered so you can descend paths. Dotfiles and dot-directories are hidden unless you start the path with a leading `.`; `__pycache__/` is also hidden unless you explicitly type that prefix.
- For a friendly command name, create a symlink in a PATH directory (and make `main.py` executable if needed), e.g.: `ln -s "$PWD/main.py" "$HOME/.local/bin/vixl"` (or set an alias `alias vixl='python /path/to/main.py'`). Completion covers the `vixl` command once the bashrc block is sourced.

---

## Features

- Vim-style modal navigation
- Command-driven DataFrame mutation
- Pandas (`pd`) and NumPy (`np`) preloaded in execution context
- Safe handling of empty tables
- Content-aware, auto-sized columns
- Right-aligned cell rendering
### Vixl – interactive DataFrame editor (curses)
- Single-line command bar at the bottom.
- Modal overlays for output and shortcuts (content-sized, up to 50% of terminal height).
- Extensions loaded from `$XDG_CONFIG_HOME/vixl/extensions` (default `~/.config/vixl/extensions`), namespaced under `df.vixl` to avoid pandas collisions.
- Persistent history at `$XDG_CONFIG_HOME/vixl/history.log` (default `~/.config/vixl/history.log`).

### Quick start
- No argument: `python main.py`
  Starts with an unsaved default DataFrame (columns `col_a`, `col_b`, `col_c`, 3 empty rows). You must Save/Save-As to persist.
- With file: `python main.py <file.csv|file.parquet>`
  Loads or creates the file; auto-detects CSV/Parquet.

### Saving / Save-As
- Ctrl+S: Save. If the file is unknown, a single-line “Save as:” prompt appears in the bottom strip. Enter path (must be .csv or .parquet); overwrites without extra confirmation. Esc cancels.
- Ctrl+T: Save & exit. If unsaved, uses the same prompt; exits only after a successful save.
- Status messages: “Saved <path>”, “Save failed: …”, “Save canceled”, “Path required”, “Save failed: use .csv or .parquet”.

### Layout & panes
- Table view for the DataFrame.
- Shared bottom strip for status/command/Save-As prompt.
- Overlays (output or shortcuts) appear centered, resize to content up to 50% of terminal height.

### Command bar (single-line)
- Enter: `:` (from df focus)
- Execute: Enter
- Cancel: Esc
- History: Ctrl+P / Ctrl+N (Ctrl+N past newest clears)
- Edit/navigation keys: Left/Right/Home/End, Backspace; Emacs-style: Alt+F / Alt+B (word fwd/back), Ctrl+W (delete word backward), Ctrl+U (kill to line start), Ctrl+H / Ctrl+D (move left/right), Ctrl+A / Ctrl+E (line start/end)

> Note: Vixl is vi-first for grid navigation, but the command bar deliberately uses Emacs-style editing keys. In a single-line, insert-first, REPL-like input (like a terminal), Emacs word-motion/kill bindings provide faster, lower-friction text editing than modal vi navigation, so they are enabled here.

### Output modal
- Appears only when there is output from a command.
- Close: Esc / q / Enter; Scroll: j / k

### Shortcuts modal
- `?` (from df) opens the shortcuts list.
- Close: Esc / q / Enter; Scroll: j / k

### DF navigation & editing
- Numeric prefixes (counts) supported for: h/j/k/l, Ctrl+J/K/H/L, ,ira / ,irb, ,dr, ,x+ / ,x-
- Repeat last change: `.` (mutations only; excludes column insert/rename/delete and command bar commands)
- Undo / Redo: `u` / `r`
- Move: h / j / k / l
- Big jumps: Ctrl+J / Ctrl+K (~5% rows down/up), Ctrl+H / Ctrl+L (~20% cols left/right)
- Row expansion (leader): `,xr` expands/collapses the current row; `,xar` expands/collapses all rows; `,xc` collapses all expansions. Expanded rows wrap vertically on word boundaries (hard-break only for overlong words) within existing column widths.
- Open command bar: `:`
- Edit cell: press `i`. Vixl suspends curses, opens **vim** in the current terminal with the cell value in a temp file, and resumes when vim exits. Exit code 0 commits the edit (with dtype coercion). Non-zero exit cancels with no changes.
- Clear cell: `x`
- Insert rows: `, i r a` (insert above), `, i r b` (insert below); Delete row: `, d r`
- Column ops: `, i c a` (insert col after), `, i c b` (insert col before), `, d c` (delete col), `, r n c` (rename col). Insert prompts for name + dtype (object, Int64, float64, boolean, datetime64[ns]).
- Go to edges: `, h` (first col), `, l` (last col), `, k` (first row), `, j` (last row)
- Adjust row lines (height): `,x+` (increase), `,x-` (decrease, min 1)
- Copy to clipboard (configurable command): `, y a` copies the entire DataFrame as TSV; `, y c` copies the current cell value. Set `"clipboard_interface_command": ["wl-copy"]` (Wayland) or `"clipboard_interface_command": ["xclip", "-selection", "clipboard", "-in"]` (X11) in `$XDG_CONFIG_HOME/vixl/config.json` (default `~/.config/vixl/config.json`).
- Preview JSON (read-only): `, p j` opens the current cell as pretty JSON in Vim (read-only flags) within the same terminal session.
- `?` opens shortcuts


### History
- Stored at `$XDG_CONFIG_HOME/vixl/history.log` (default `~/.config/vixl/history.log`).
- Command bar history navigation: Ctrl+P / Ctrl+N.

### Extensions
- Location: `$XDG_CONFIG_HOME/vixl/extensions/*.py` (default `~/.config/vixl/extensions/*.py`)
- Loaded at startup; functions are exposed under `df.vixl.<name>` to avoid pandas attribute collisions.
- Mutation contract:
  - Explicit commit required for extension calls: return `(df, True)`, or set `commit_df = True` and assign `df = new_df`.
  - User-written commands commit only when they assign to `df` (e.g., `df["col"] = ...` or `df = df.assign(...)`). Read-only commands leave the DataFrame unchanged.
- Config: `$XDG_CONFIG_HOME/vixl/config.json` (default: `~/.config/vixl/config.json`). Supported keys:
  - `cmd_mode.tab_fuzzy_expansions_register` (list of strings) for cmd-mode Tab insertions.
  - `clipboard_interface_command` (list of strings) — argv to run when copying to the clipboard (reads from stdin). Examples:
    - Wayland: `["wl-copy"]`
    - X11: `["xclip", "-selection", "clipboard", "-in"]`
  - `python_path` (string) — path to a venv’s python executable (e.g. `/home/me/.venv/bin/python`). If set, Vixl adds that interpreter’s `site-packages` to `sys.path` before loading extensions and running cmd-mode code so imports can resolve user-installed packages. For compiled wheels, the venv Python major/minor should match Vixl’s runtime or imports may fail.
  Example:
  ```json
  {
    "python_path": "/home/me/.venv/bin/python",
    "clipboard_interface_command": ["wl-copy"],
    "cmd_mode": {
      "tab_fuzzy_expansions_register": [
        "df.vixl.distribution_ascii_bar(bins=10)",
        "df.pivot()",
        "df.info()"
      ]
    }
  }
  ```
- Config + completions path respects `$XDG_CONFIG_HOME` (falls back to `~/.config/vixl`).
- Examples (save under `$XDG_CONFIG_HOME/vixl/extensions/`):
   1) multiply_cols (explicit commit)
      ```python

     def multiply_cols(df, col_a, col_b, out_col="product"):
         df[out_col] = df[col_a] * df[col_b]
         return df, True
     ```
  2) add_ratio (commit flag or tuple)
     ```python
     def add_ratio(df, num_col, den_col, out_col="ratio"):
         df[out_col] = df[num_col] / df[den_col]
         commit_df = True  # honored if you set it and assign df; or return (df, True)
         return df, True
     ```
  3) top_n (read-only, no commit)
     ```python
     def top_n(df, col, n=5):
         return df.sort_values(col, ascending=False).head(n)
     ```
  4) ascii_bar (fun display; no commit)
     ```python
     def ascii_bar(df, col, width=40):
         vals = df[col].fillna(0)
         maxv = vals.max() if len(vals) else 0
         lines = []
         for v in vals:
             bar_len = 0 if maxv == 0 else int(width * (v / maxv))
             lines.append("|" + "█" * bar_len)
         return "\n".join(lines)
     ```
     Usage: `df.vixl.ascii_bar("col_a")` → shows a simple bar chart in the output modal.
  5) normalize_cols (explicit commit)
     ```python
     def normalize_cols(df, cols, prefix="norm_"):
         for c in cols:
             mx = df[c].max()
             mn = df[c].min()
             df[f"{prefix}{c}"] = (df[c] - mn) / (mx - mn) if mx != mn else 0
         return df, True
     ```
- Usage examples in cmd:
  - `df.vixl.multiply_cols("col_a", "col_b", out_col="prod")` (commits via tuple)
  - `df.vixl.top_n("col_a", 3)` (read-only; output modal)
  - `df.vixl.ascii_bar("col_a")` (bar graph in modal)

### Removed / changed features
- Leader commands (`,ya`, `,yap`, `,yio`, `,o`, `,df`) removed.
- Multi-line command pane removed; output pane is no longer side-by-side—now modal only.
- Explicit save and save-on-exit

### Editing philosophy

- The grid is for navigation and selection. Pressing `i` launches vim in the current terminal with the cell value in a temp file; exiting vim with status 0 commits the change (dtype-coerced), non-zero cancels.
- Structural or multi-cell mutations remain explicit Python commands typed into the command bar (`:`).
- There are no inline cell modes; the clipboard command is configurable via `clipboard_interface_command` in `$XDG_CONFIG_HOME/vixl/config.json` (default `~/.config/vixl/config.json`).

---

## Code Layout

The repository reflects the current, runnable implementation of Vixl.

All Python files live in the project root:

- `main.py` – application entrypoint and bootstrap
- `orchestrator.py` – main event loop and coordination
- `app_state.py` – core application state and invariants
- `file_type_handler.py` – file loading and saving logic
- `command_executor.py` – command execution sandbox
- `grid_pane.py`, `command_pane.py`, `output_pane.py` – UI panes

Each file represents a clear product responsibility, with one primary class per
file.

---

## Philosophy

- Terminal-native, curses-based UI
- Vim-inspired modal interaction
- Explicit, inspectable data manipulation
- Dense, information-first rendering
- Minimal hidden behavior

For a detailed description of scope and constraints, see `ProjectScope.md`.
