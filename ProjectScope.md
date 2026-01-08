# Project Scope

## 1. Project Overview

This document reflects the **current, implemented reality** of the project as of v0, not aspirational design.

This project aims to build a **Vim-first, terminal-native spreadsheet editor** that replaces roughly 80% of Microsoft Excel’s day-to-day functionality for keyboard-driven users.

The product prioritizes speed, scriptability, transparency, and tight integration with the Python data ecosystem.

This is not an Excel UI clone. It is a power-user alternative optimized for working with tabular data inside the terminal.

---

## 2. Core Design Principles

- Vim-first interaction model with modal editing
- Terminal-native (TUI only)
- Product-first code organization
- Flat file structure (no directories)
- One class per file
- Fast feature velocity over architectural purity (v0)
- Architectural clarity and separation (v1+)

---

## 3. Explicit Non-Goals (v0)

Out of scope for v0:

- Excel-style formulas
- Pivot tables
- VBA / macro systems
- Rich formatting (fonts, colors beyond selection)
- Collaboration or multi-user editing
- GUI or web interface
- Multiple sheets or workbooks

---

## 4. Application Entry & Control Flow

### main.py

Responsibilities:
- Parse CLI arguments
- Initialize core objects
- Hand control to the orchestrator

Contains no rendering, key handling, or business logic.

### orchestrator.py

Responsibilities:
- Own the main event loop
- Dispatch input to mode handlers
- Coordinate application state, rendering, and feature handlers

---

## 5. Data Model & Editing Philosophy

- Data is represented internally as a Pandas DataFrame
- Pandas is a first-class user API
- Direct cell editing is supported
- Advanced transformations are done via explicit Pandas / NumPy commands

Example:
```
: df.col_a.value_counts()
: df["price"] = df["price"] * 1.2
```

---

## 6. Command-Based Data Manipulation

- Users manipulate data via Python expressions
- Expressions operate on:
  - df (active DataFrame)
  - np (NumPy)

Characteristics:
- Explicit execution
- No auto-recalculation
- Transparent behavior

---

## 7. Navigation & Highlight Model

Navigation and highlighting are finalized and stable.

Supported highlight modes:
- Cell-wise (h j k l)
- Row-wise (J / K)
- Column-wise (H / L)

Rules:
- Cursor never enters hidden rows
- Navigation jumps over truncated regions (`...`)
- Highlight is always visible

---

## 7.5 Insert Mode Philosophy

Insert mode is **command-prefill only**, not a text editor.

- `i` generates a Pandas mutation command based on highlight scope
- Prefilled command opens in COMMAND mode
- User edits and executes explicitly

Examples:
```
# Cell
df.loc[row, 'col'] = <value>

# Row
df.loc[row] = { ... }

# Column
df = df.rename(columns={'old': 'old'})
```

Selection mirrors Vim visual mode only.

Supported:
- Cell-wise selection
- Line-wise selection
- Block-wise selection
- Yank, cut, paste, delete

Out of scope:
- Named ranges
- Persistent multi-region selection

---

## 8. Charts & Visualization (In Scope)

Supported terminal-renderable charts:
- Histograms
- Line charts
- Bar charts
- Scatter plots

Charts are ephemeral inspection tools, not embedded spreadsheet objects.

---

## 9. Undo / Redo

Undo and redo are first-class features.

Applies to:
- Cell edits
- Structural changes
- Command-based DataFrame mutations

---

## 10. File I/O & Persistence

Supported formats (v0):
- CSV
- Parquet

Characteristics:
- Explicit save
- Auto-save on exit
- Dirty-state tracking

---

## 11. Mode System

This section distinguishes between **v0 implemented modes** and **v1 formalized modes**.

Modes implemented in v0:
- Normal
- Command

Modes formalized in v1:
- Insert
- Cell edit
- Header edit

Insert is a **Normal-mode shortcut** that transitions into Command mode.

Cell/Header edit modes are deferred.

The application is modal.

Expected modes:
- Normal
- Insert
- Cell edit
- Header edit
- Command

Each mode has a dedicated handler class.

---

## 12. Code Organization Rules

These rules reflect **v0 constraints**, not permanent architectural doctrine.

- All files live in the project root
- Each file defines exactly one class
- Files represent product responsibilities
- Related files share naming prefixes

Example:
```
normal_mode_navigation_handler.py
normal_mode_row_ops_handler.py
```

---

## 13. Target User

- Developers
- Data scientists
- Analysts
- Vim users

Assumes keyboard fluency and basic Python familiarity.

---

## 14. v0 Success Criteria

The project is successful when:

- Users can edit datasets comfortably in the terminal
- Common Excel workflows are keyboard-driven
- Data manipulation is more transparent than Excel
- main.py never grows with new features

---

## 15. v1 Scope & Direction

v1 transitions the project from a fast-moving prototype into a stable, extensible editor while preserving the Vim-first, terminal-native philosophy.

v1 characteristics:
- Modular directory-based code organization
- Clear separation between core state, UI, modes, and commands
- Fully realized mode system (Insert, Cell edit, Header edit)
- Undo/redo correctness guarantees across all mutations
- Stable command surface for user workflows
- Charts treated as first-class inspection commands

Explicit non-goals remain unchanged unless stated elsewhere.
