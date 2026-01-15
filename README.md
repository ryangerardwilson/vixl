# Vixl

Vixl is a **Vim-first, terminal-native spreadsheet editor** for fast, explicit
manipulation of tabular data using Pandas and NumPy.

It is designed for users who prefer keyboard-driven workflows and want full
transparency over how their data is transformed.

---

## Installation

### Prebuilt binary (Linux x86_64)

The fastest way to get Vixl is to install the prebuilt PyInstaller binary that
ships with each GitHub release:

```bash
curl -fsSL https://raw.githubusercontent.com/ryangerardwilson/vixl/main/install.sh | bash
  ```

#### Debugging tips
- "Unknown command" → name not present in `cmd_mode.command_register` or config JSON is invalid.
- "Mutating command produced no parquet" → your command never wrote to `VIXL_OUT_PARQUET`.
- Command prints nothing? Write to `VIXL_OUT_TEXT` or stdout so Vixl can show it.
- SQL/text args with spaces: quote them (`"select * from users"`).

- Example `~/.config/vixl/extensions.py`:


  ```python
  def multiply_cols(df, col_a, col_b, out_col="product"):
      df[out_col] = df[col_a] * df[col_b]
      return df, True

  def top_n(df, col, n=5):
      return df.sort_values(col, ascending=False).head(n)

  def add_ratio(df, num_col, den_col, out_col="ratio"):
      df[out_col] = df[num_col] / df[den_col]
      return df, True
  ```
- Usage examples in cmd:
  - `df.vixl.multiply_cols("col_a", "col_b", out_col="prod")` (commits via tuple)
  - `df.vixl.top_n("col_a", 3)` (read-only; output modal)
  - `df.vixl.add_ratio("col_a", "col_b")`

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
