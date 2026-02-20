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

## Command-line usage

```bash
vixl [path]   # open an existing CSV, Parquet, XLSX, or HDF5 file (creates if missing)
vixl -v       # print version
vixl -u       # upgrade to the latest release
vixl -h       # show help/usage summary
```

Launch without a path to start in an empty, unsaved workbook seeded with
`col_a`/`col_b`/`col_c`.

## Keyboard shortcuts

Vixl is modal and follows Vim-inspired navigation. Shortcuts are grouped by the
active context.

### Global

- `Ctrl+C`, `Ctrl+Q`, or `q` (while the grid has focus) – exit immediately
- `Ctrl+S` – save
- `Ctrl+T` – save and exit (only exits after a successful save)
- `?` – open the shortcuts overlay

### Command bar (entered with `:`)

- `Enter` – execute the current command buffer
- `Esc` – cancel and return to DF mode
- `Ctrl+P` / `Ctrl+N` – previous/next command history
- Arrow keys / `Home` / `End` / `Backspace` – standard line editing

### Output or shortcuts overlay

- `Esc`, `q`, or `Enter` – close the overlay
- `j` / `k` – scroll

### DF mode navigation & editing

- `h` / `j` / `k` / `l` – move left/down/up/right
- `H` / `L` – previous/next sheet (multi-sheet files)
- `Ctrl+J` / `Ctrl+K` – jump ~5% rows down/up
- `Ctrl+H` / `Ctrl+L` – jump ~20% columns left/right
- `:` – open the command bar
- `i` – edit the focused cell in Vim (visual selections bulk-fill)
- `x` – clear the focused cell
- `v` – toggle visual block selection
- `d` (in visual) – clear all selected cells
- `, y c` – copy the focused cell (or visual selection) as TSV
- `, y a` – copy the full DataFrame as TSV
- `, i r a` / `, i r b` – insert row above/below
- `, d r` – delete focused row (or selected rows)
- `, i c a` / `, i c b` – insert column left/right
- `, d c` – delete focused column (or selected columns)
- `, r n c` – rename current column
- `,xr` – toggle expansion for the current row
- `,xar` – toggle expansion for all rows
- `,xc` – collapse all expanded rows
- `,conf` – open the Vixl config (`~/.config/vixl/config.json`) in Vim (auto-reload on exit)
- `, h` / `, l` – jump to first/last column
- `, k` / `, j` – jump to first/last row
- `, p j` – preview the current cell as pretty JSON in Vim (read-only)

## Special command syntax

Commands are entered via the command bar (`:`) and executed in a sandbox with
`df` (current DataFrame), `pd`, and `np` preloaded.

- Assigning to `df` or returning `(df, True)` from arbitrary expressions commits
  the DataFrame; read-only commands leave it unchanged

#### Debugging tips
- No external command register exists—keep data transformations inside the
  in-process Python sandbox.
- Command prints nothing? Write to stdout so Vixl can show it.
- SQL/text args with spaces: quote them (`"select * from users"`).

### Removed / changed features
- Leader commands (`,ya`, `,yap`, `,yio`, `,o`, `,df`) removed.
- Multi-line command pane removed; output pane is no longer side-by-side—now modal only.
- Explicit save and save-on-exit

### Editing philosophy

- The grid is for navigation and selection. Pressing `i` launches vim in the current terminal with the cell value in a temp file; exiting vim with status 0 commits the change (dtype-coerced), non-zero cancels.
- Structural or multi-cell mutations remain explicit Python commands typed into the command bar (`:`).
- There are no inline cell modes; the clipboard command is configurable via `clipboard_interface_command` in `$XDG_CONFIG_HOME/vixl/config.json` (default `~/.config/vixl/config.json`).
- Use the leader sequence `,conf` to edit the application config; Vixl automatically reloads the file after you quit Vim.

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
