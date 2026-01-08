# Vixl

Vixl is a **Vim-first, terminal-native spreadsheet editor** designed for fast, explicit manipulation of tabular data using the Python data ecosystem.

This repository currently contains a **single flat implementation** of the application, reflecting the active, runnable state of the project.

Earlier versioned directories (such as `v2/`) were used during development but have been flattened into the project root to preserve the v0 design constraint of **no directory-based architecture**.

## Running the App

Run the application directly via the root entrypoint:

```bash
python main.py <csv-file>
```

## Code Layout

All Python files live in the project root, following the v0 rules:

- One class per file
- Product-responsibility-based filenames
- Flat structure (no packages)

Key files:

- `main.py` – Application entrypoint (CLI parsing + bootstrap)
- `orchestrator.py` – Main event loop and coordination
- `app_state.py` – Core application state
- `grid_pane.py`, `command_pane.py`, `output_pane.py` – UI panes

## Design Principles

- Vim-style modal interaction
- Terminal-only (curses-based TUI)
- Pandas DataFrame as the core data model
- Explicit, command-driven data mutation
- Thin root entrypoint; logic lives in versioned implementations

For the authoritative description of scope and philosophy, see `ProjectScope.md`.
