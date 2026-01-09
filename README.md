# Vixl

Vixl is a **Vim-first, terminal-native spreadsheet editor** for fast, explicit manipulation of tabular data using Pandas and NumPy.

It is designed for users who prefer keyboard-driven workflows and want full transparency over how their data is transformed.

---

## Running the App

Run the application via the root entrypoint:

```bash
python main.py <csv-or-parquet-file>
```

- CSV and Parquet files are supported
- If the file does not exist, a blank file is created automatically

---

## Features

- Vim-style modal navigation
- Command-driven DataFrame mutation
- Pandas (`pd`) and NumPy (`np`) preloaded in execution context
- Safe handling of empty tables
- Content-aware, auto-sized columns
- Right-aligned cell rendering
- Persistent global command history (`~/.vixl_history`)
- Explicit save and save-on-exit

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

Each file represents a clear product responsibility, with one primary class per file.

---

## Philosophy

- Terminal-native, curses-based UI
- Vim-inspired modal interaction
- Explicit, inspectable data manipulation
- Dense, information-first rendering
- Minimal hidden behavior

For a detailed description of scope and constraints, see `ProjectScope.md`.
