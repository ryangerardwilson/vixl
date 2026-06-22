# Product Engineer Role

## Purpose

Own vixl-specific facts that should not live in root generalists.

## Load Guidance

Load this file for `vixl` implementation, CLI/TUI, installer, release, storage,
configuration, or project-specific product work.

## Owns

- repo-local product and implementation facts
- CLI/TUI contract, command grammar, config, storage, and installer constraints
- release, upgrade, and verification expectations specific to this app

## Project Context

- Vixl is a Go/Bubble Tea terminal spreadsheet editor.
- The stable Go data path supports CSV, TSV, Parquet, XLSX, HDF5, and
  read-only XLS.
- `vixl open` starts an unsaved seeded workbook.
- `vixl open <path>` loads or creates CSV/TSV, Parquet, XLSX, and HDF5 files.
- XLSX, HDF5, and Vixl workbook Parquet load/save preserve multiple
  worksheets; `H` and `L` move to the previous and next sheet in the TUI.
- Workbook-capable files show a compact bottom sheet indicator even when they
  currently have one sheet.
- Transient TUI notifications render on a separate line above the sheet
  indicator and then disappear.
- Typed-input states render a blinking block cursor.
- `,repl` toggles a right-side Python REPL. The REPL loads the active sheet
  into `df`, preloads numpy as `np` and pandas as `pd`, and prefers
  `VIXL_REPL_PYTHON`, then `VIXL_HDF_PYTHON`, then the vixl-managed HDF
  runtime, then `python3`/`python`. Hiding the sidebar preserves the session
  and visible REPL history; `Ctrl+L` clears the REPL screen.
- `,ns` creates and switches to a new sheet in workbook-capable files.
- `,rns` opens a modal to rename the active sheet in workbook-capable files.
- CSV/TSV are single-table formats; Vixl does not show the sheet indicator
  there and rejects multi-sheet saves to CSV/TSV.
- Single-sheet Parquet remains a normal table. Multi-sheet Parquet uses
  `vixl.workbook.v1` metadata and a long-form cell table.
- `vixl open <path>.xls` opens legacy XLS files as read-only imports; direct
  XLS saves are not supported.
- HDF5 read/write runs through an embedded Python bridge and the
  installer-managed PyTables runtime under `~/.vixl/hdf`; libhdf5 is not
  compiled into the Go binary.
- Column widths changed in the TUI persist in XLSX native column widths and
  Parquet metadata. CSV/TSV saves do not persist column widths.
- Columns without saved/custom widths render from content-fit widths with
  bounded padding rather than the old fixed-width default.
- `,xar` toggles all rows between collapsed single-line cells and expanded
  wrapped cell rendering.
- Vixl's current grid model treats cell values as strings; Parquet saves write
  string columns rather than preserving prior physical types.
- `vixl config` opens the real user config in `$VISUAL`, then `$EDITOR`, then `vim`.
- `help`, `version`, `upgrade`, and `config` must stay fast and free of TUI startup.
- Release artifacts are Linux x64 Go binaries installed by `install.sh`; the
  installer provisions the HDF5/PyTables runtime separately.

## Current Modules

- `cmd/vixl/` - executable entrypoint
- `internal/cli/` - command dispatch and config/upgrade handoff
- `internal/app/` - Bubble Tea grid UI
- `internal/sheet/` - file-format load/save, metadata, and mutation invariants
- `internal/config/` - user config path
- `internal/version/` - stamped release version

## Testing Workflow

- Run all tests with `go test ./...`.
- Keep tests focused on command dispatch, file load/save, metadata persistence,
  installer behavior, and grid mutation invariants.
