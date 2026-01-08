# Project Scope

## 1. Project Overview

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

## 7. Selection Model

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
