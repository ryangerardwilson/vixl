# Project Scope

## 1. Project Overview

Vixl is a **Vim-first, terminal-native spreadsheet editor** for fast, explicit
manipulation of tabular data inside the terminal.

The project prioritizes speed, density, scriptability, and transparency, with
tight integration into the Python data ecosystem. Vixl is not an Excel UI
clone; it is a power-user tool optimized for keyboard-driven workflows and
inspectable data transformations.

---

## 2. Core Design Principles

- Vim-first, modal interaction model
- Terminal-native (curses-based TUI only)
- Pandas DataFrame as the core data model
- Explicit, command-driven data mutation
- Flat project structure (no packages)
- One primary class per file
- Clarity and locality over abstraction
- Release workflow produces self-contained binaries via PyInstaller (Linux x86_64)

---

## 3. Explicit Non-Goals

The following are intentionally out of scope:

- Excel-style formulas or recalculation engine
- Pivot tables
- Macro or VBA-style systems
- Rich formatting beyond selection and highlighting
- Multiple sheets or workbooks
- GUI or web interface
- Real-time collaboration or multi-user editing

---

## 4. Application Entry & Control Flow

### main.py

Responsibilities:
- Parse CLI arguments
- Initialize file handling and application state
- Hand control to the orchestrator

`main.py` contains no rendering, key handling, or business logic and is
expected to remain thin.

### orchestrator.py

Responsibilities:
- Own the main event loop
- Route input based on focus and mode
- Coordinate application state, rendering, and command execution

---

## 5. Data Model & Editing Philosophy

- All data is represented internally as a Pandas DataFrame
- Pandas and NumPy are first-class user APIs (`df`, `pd`, `np`)
- Direct cell editing is supported via explicit commands
- Structural and bulk changes are performed through Python expressions

Data invariants:
- If a DataFrame has columns, it always has at least one row
- Empty tables are safe to render, navigate, and persist

---

## 6. Command Execution Model

Users manipulate data by executing Python expressions explicitly in a single in-process sandbox.

Execution context provides:
- `df`: active DataFrame
- `pd`: pandas
- `np`: numpy

Characteristics:
- Explicit execution
- No auto-recalculation
- Output is captured and displayed
- Errors do not mutate application state
- Successful commands are persisted to history
- Commit semantics: assigning to `df`, returning `(df, True)`, or setting `commit_df = True` updates the active DataFrame; otherwise the DataFrame is unchanged.

---

## 7. Navigation & Highlight Model

Navigation and selection follow Vim-inspired semantics.

Supported highlight modes:
- Cell-wise (`h j k l`)
- Row-wise (`J / K`)
- Column-wise (`H / L`)
- Visual block (`v` to start/extend a rectangular selection)

Rules:
- Cursor always remains within visible, valid cells
- Highlight is always visible (visual selections are rendered in-grid)
- Navigation is column- and row-based, not pixel-based

---

## 8. Editing & Command Interaction

- DF mode handles navigation, visual selection, and per-cell actions.
- Pressing `i` opens **vim** in the current terminal with the focused cell value in a temp file; exiting vim with status 0 commits the edit (dtype-coerced), non-zero cancels. When visual mode is active, `i` opens Vim once to collect a replacement value and bulk-fills the selected rectangle.
- Visual mode (`v`) provides a rectangular selection; `d` clears all selected cells (dtype-aware) and Esc exits visual.
- The grid never enters an inline text-editing mode; all inline editing was removed in favor of vim.
- Structural/bulk mutations (insert columns, run pandas transforms, etc.) remain explicit Python commands typed into the command bar (`:`).
- The command bar continues to provide a sandboxed `df`/`pd`/`np` context for arbitrary expressions.

---

## 9. Rendering Model

- Column widths are computed dynamically based on content
- Each column width is capped to preserve density
- Cell and header contents are right-aligned
- Rendering is purely visual and does not mutate data

---

## 10. File I/O & Persistence

Supported formats:
- CSV
- Parquet

Characteristics:
- Files are created automatically if missing
- Explicit save and save-on-exit
- File-type handling is centralized
- Data invariants are preserved on disk

---

## 11. Command History

### Architecture
- Entry: `main.py` → `LoadingScreen` → `Orchestrator`
- Layout: table + shared bottom strip (status/command/prompt); overlays for output/shortcuts (content-sized, ≤50% terminal height).
- Execution: single in-process sandboxed `df`. Commits occur only when an extension explicitly commits or when the user assigns to `df` (e.g., `df[...] = ...`, `df = df.assign(...)`). Read-only commands leave the DataFrame unchanged.
- Saving: Save-As prompt if no file handler; Ctrl+S/Ctrl+T handle save/save-exit.
- History: `~/.config/vixl/history.log`; history nav in command bar (Ctrl+P/Ctrl+N). Successful command executions and successful `:%fz/...` / `:%fz#/...` loads are recorded so they can be recalled.
- Extensions: defined in `~/.config/vixl/extensions.py`; imports are disallowed (only builtins + `pd`/`np` are available); config at `~/.config/vixl/config.json`.
- External commands: registered in `cmd_mode.command_register`, invoked as `!name ...`. Vixl writes the current df to a temp file and appends the input path as the final argv element. Commands declare `kind` (`mutate` requires writing `VIXL_OUT_PARQUET` to commit df; `print` shows output only). Unknown command names are rejected.

### Features
- No-arg launch: default df with cols col_a/col_b/col_c, 3 empty rows, unsaved buffer.
- Single-line command bar; Enter executes; Esc cancels; Ctrl+P/Ctrl+N history.
- Output modal appears only when there is output; shortcuts modal via `?`; both close with Esc/q/Enter; j/k scroll.
- DF navigation/editing: h/j/k/l, H/L, J/K, `:`, `i` (launch vim to edit current cell), `x`, `, i r a`, `, i r b`, `, d r`, `, i c a`, `, i c b`, `, d c`, `, r n c`, `, y a`, `, y c`, `,xr`, `,xar`, `,xc`, `,x+`, `,x-`, `, h`, `, l`, `, k`, `, j`, `, p j`. Expanded rows wrap on word boundaries (hard-break only for overlong words). Vim-based editing works regardless of expansion state.
- Save-As flow: inline prompt on Ctrl+S/Ctrl+T when unsaved; validates .csv/.parquet; Ctrl+T exits only after successful save.
- Overlays auto-size to content up to 50% of terminal height, centered.
- Parquet support requires `pyarrow` (installed via requirements.txt).

### Keymap (canonical)
- Global: Ctrl+C/Ctrl+X exit; Ctrl+S save; Ctrl+T save & exit (after save); ? shortcuts.
- Command bar: `:` enter; Enter execute; Esc cancel; Ctrl+P/Ctrl+N history; arrows/Home/End/Backspace edit.
- Output/shortcuts overlay: Esc/q/Enter close; j/k scroll.
- DF mode: h/j/k/l move; H/L column highlight; J/K row highlight; Ctrl+J / Ctrl+K (~5% rows) and Ctrl+H / Ctrl+L (~20% cols) big jumps; `:` command bar; `i` open vim for current cell; `x` clear cell; `, i r a` / `, i r b` insert rows; `, d r` delete row; `, i c a` / `, i c b` insert columns; `, d c` delete column; `, r n c` rename column; `,xr` toggle current row expansion; `,xar` toggle all rows; `,xc` collapse all expansions; `,x+` / `,x-` adjust row height; `, h` first column; `, l` last column; `, k` first row; `, j` last row; `, y a` / `, y c` copy to clipboard using the configured command; `, p j` preview cell as pretty JSON (vim read-only flags); `?` shortcuts.

### File locations
- History: `$XDG_CONFIG_HOME/vixl/history.log` (default `~/.config/vixl/history.log`)
- Extensions: `$XDG_CONFIG_HOME/vixl/extensions.py`
- Config: `$XDG_CONFIG_HOME/vixl/config.json`
- Default df: created in `main.py` when no arg is provided.

- The history file is the single source of truth
- Only successful commands are recorded
- Non-adjacent duplicate commands are allowed

---

## 12. Code Organization Rules

- All Python files live in the project root
- Each file represents a clear product responsibility
- No prototype or versioned directories

---

## 13. Target User

Vixl is designed for:
- Developers
- Data scientists
- Analysts
- Vim users

Users are expected to be comfortable with the keyboard and basic Python
concepts.

---

## 14. Project Success Criteria

The project is successful when:
- Users can comfortably edit datasets entirely in the terminal
- Common spreadsheet workflows are keyboard-driven
- Data manipulation is explicit and inspectable
- The codebase remains understandable and free of hidden behavior
