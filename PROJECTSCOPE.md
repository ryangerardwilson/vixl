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

Users manipulate data by executing Python expressions explicitly.

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

---

## 7. Navigation & Highlight Model

Navigation and selection follow Vim-inspired semantics.

Supported highlight modes:
- Cell-wise (`h j k l`)
- Row-wise (`J / K`)
- Column-wise (`H / L`)

Rules:
- Cursor always remains within visible, valid cells
- Highlight is always visible
- Navigation is column- and row-based, not pixel-based

---

## 8. Insert & Command Interaction

In **df mode**, interaction is strictly modal and intentional.

- **df Normal mode** is used for navigation and selection only
- **df Insert mode** is an intent-to-command bridge, not a free-form spreadsheet editor

Behavior of df Insert mode:

- `i` generates a context-aware Pandas mutation command
- The prefilled command opens in the command pane
- Users edit and execute explicitly in **command pane Insert mode**

The grid is a navigation and visualization surface, never a text editor. All
text entry occurs in the command pane, and all data mutation flows through
explicit Python commands.

Selection mirrors Vim visual mode semantics.

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
- Execution: sandboxed `df`; natural commands auto-commit; extension calls require explicit commit (`(df, True)` or `commit_df=True` + `df = ...`).
- Saving: Save-As prompt if no file handler; Ctrl+S/Ctrl+T handle save/save-exit.
- History: `~/.config/vixl/history.log`; history nav in command bar (Ctrl+P/Ctrl+N).
- Extensions: loaded from `~/.config/vixl/extensions/`; config at `~/.config/vixl/config.py` (AUTO_COMMIT flag).

### Features
- No-arg launch: default df with cols col_a/col_b/col_c, 3 empty rows, unsaved buffer.
- Single-line command bar; Enter/Ctrl+E executes; Esc cancels; Ctrl+P/Ctrl+N history.
- Output modal appears only when there is output; shortcuts modal via `?`; both close with Esc/q/Enter; j/k scroll.
- DF navigation/editing: h/j/k/l, H/L, J/K, `:`, `i`, `, e`, `, c c`, `, d c`, `, n r`, `, v` (external edit via `$VISUAL`/`$EDITOR`, syncs back with status), `, y` (copy df to clipboard as TSV via wl-copy).
- Save-As flow: inline prompt on Ctrl+S/Ctrl+T when unsaved; validates .csv/.parquet; Ctrl+T exits only after successful save.
- Overlays auto-size to content up to 50% of terminal height, centered.

### Keymap (canonical)
- Global: Ctrl+C/Ctrl+X exit; Ctrl+S save; Ctrl+T save & exit (after save); ? shortcuts.
- Command bar: : enter; Enter/Ctrl+E execute; Esc cancel; Ctrl+P/Ctrl+N history; arrows/Home/End/Backspace edit.
- Output/shortcuts overlay: Esc/q/Enter close; j/k scroll.
- DF normal: h/j/k/l move; H/L col highlight; J/K row highlight; Ctrl+J / Ctrl+K (~5% rows) and Ctrl+H / Ctrl+L (~20% cols) big jumps; : command; i edit; , e edit; , c c empty edit; , d c clear; , n r insert row; , v external edit (opens `$VISUAL`/`$EDITOR`, status shows while syncing); , h first col; , l last col; , k first row; , j last row; , y copy df to clipboard (TSV via wl-copy); ? shortcuts.
- Cell insert: type; Backspace; Esc commits to cell_normal.
- Cell normal: h/l move within buffer; , e / , c c / , d c / , n r; , v external edit (returns cursor to start after sync); i insert; Esc back to df normal.

### File locations
- History: `~/.config/vixl/history.log`
- Extensions: `~/.config/vixl/extensions/`
- Config: `~/.config/vixl/config.py` (AUTO_COMMIT)
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
