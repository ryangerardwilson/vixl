# Vixl Project Scope

Vixl is a Go/Bubble Tea terminal spreadsheet editor for CSV, TSV, Parquet,
XLSX, HDF5, and read-only XLS files.

## In Scope

- Open an empty seeded workbook with `vixl open`.
- Open or create CSV/TSV, Parquet, XLSX, and HDF5 files with
  `vixl open <path>`.
- Open legacy XLS files as read-only imports.
- Navigate cells with Vim-style movement.
- Navigate workbook sheets with `H` and `L`.
- Show a compact bottom sheet indicator for workbook-capable files.
- Show transient notifications on a separate line above the sheet indicator.
- Show a blinking block cursor whenever the TUI is collecting typed input.
- Toggle a right-side Python REPL with `,repl`, with the active sheet loaded
  into `df`, numpy as `np`, and pandas as `pd`.
- Keep the REPL session and screen state when the sidebar is hidden; `Ctrl+L`
  clears the REPL screen.
- Add a new sheet with `,ns` in workbook-capable files.
- Rename the active sheet with a `,rns` modal in workbook-capable files.
- Edit focused cells.
- Insert/delete rows and columns.
- Rename columns.
- Resize focused columns in the TUI.
- Auto-size columns from content when no saved/custom width exists.
- Expand/collapse all row heights with `,xar`.
- Save in CSV/TSV, Parquet, XLSX, and HDF5 format.
- Preserve multiple sheets when loading/saving XLSX workbooks.
- Preserve multiple sheets when loading/saving HDF5 files through the
  installer-managed PyTables runtime.
- Preserve multiple sheets in Parquet by using Vixl workbook metadata
  `vixl.workbook.v1`; single-sheet Parquet remains a normal table.
- Keep CSV/TSV as single-table formats and reject multi-sheet saves to those
  formats.
- Persist Vixl column widths in XLSX native column widths and Parquet
  `vixl.ui.v1` metadata.
- Provision a vixl-managed HDF5/PyTables Python runtime under `~/.vixl/hdf`
  from `install.sh`.
- Treat visible cell values as strings; Parquet saves write string columns in
  the current runtime.
- Keep release and install as a single Linux x64 Go binary.

## Out Of Scope

- Python runtime embedding.
- Legacy dynamic data command execution.
- XLS write support.
- Compiling libhdf5 into the Go release binary.
- Side-by-side output panes or Python command sandboxes.

## Architecture

- `cmd/vixl/` is the executable entrypoint.
- `internal/cli/` owns command dispatch.
- `internal/app/` owns the Bubble Tea grid.
- `internal/sheet/` owns file-format load/save, metadata, and mutation
  invariants.
- `internal/config/` owns the user config path.
