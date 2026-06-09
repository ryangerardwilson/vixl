# Vixl Project Scope

Vixl is a Go/Bubble Tea terminal spreadsheet editor for CSV and TSV files.

## In Scope

- Open an empty seeded workbook with `vixl open`.
- Open or create CSV/TSV files with `vixl open <path>`.
- Navigate cells with Vim-style movement.
- Edit focused cells.
- Insert/delete rows and columns.
- Rename columns.
- Save in CSV/TSV format.
- Keep release and install as a single Linux x64 Go binary.

## Out Of Scope

- Python runtime embedding.
- Legacy dynamic data command execution.
- Parquet, XLSX, and HDF5 runtime support.
- Side-by-side output panes or Python command sandboxes.

## Architecture

- `cmd/vixl/` is the executable entrypoint.
- `internal/cli/` owns command dispatch.
- `internal/app/` owns the Bubble Tea grid.
- `internal/sheet/` owns CSV/TSV load, save, and mutation invariants.
- `internal/config/` owns the user config path.
