# Vixl

Vixl is a Vim-first terminal spreadsheet editor written in Go with a Bubble Tea
TUI. The Go runtime supports CSV, TSV, Parquet, XLSX, HDF5, and read-only XLS
workbooks.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/ryangerardwilson/vixl/main/install.sh | bash
```

Install from source:

```bash
bash install.sh from "$(pwd)"
```

## Usage

```bash
vixl open
vixl open data.csv
vixl open data.parquet
vixl open data.xlsx
vixl config
vixl help
vixl version
vixl upgrade
```

`vixl open` starts an unsaved workbook seeded with `col_a`, `col_b`, and
`col_c`. `vixl open data.csv` loads or creates a CSV/TSV file.
`vixl open data.parquet` and `vixl open data.xlsx` load or create Parquet and
XLSX files. Legacy `.xls` files can be opened, but saves must target `.xlsx`,
`.parquet`, `.csv`, or `.tsv`.

Column widths changed with `>` and `<` are saved in XLSX native column widths
and Parquet `vixl.ui.v1` metadata. CSV and TSV saves keep only cell data.
When a column has no saved/custom width, Vixl sizes it from visible content so
short fields such as two-digit ages stay compact. XLSX, HDF5, and Vixl
workbook Parquet files preserve and save multiple sheets; `H` and `L` move to
the previous and next sheet, and a compact sheet indicator is shown on the
bottom line. Transient notifications appear on the line above that indicator.
Typed-input states show a blinking block cursor.
`,ns` adds a new sheet in workbook-capable files. CSV and TSV remain
single-table formats, so they do not show the sheet indicator and cannot store
extra sheets. Single-sheet Parquet remains a normal columnar table. Multi-sheet
Parquet uses Vixl metadata (`vixl.workbook.v1`) and a long-form cell table.
`,rns` opens a modal to rename the active sheet in workbook-capable files.
`,repl` toggles a right-side Python REPL with the active sheet loaded into
`df`, `numpy` preloaded as `np`, and `pandas` preloaded as `pd`. Hiding the
sidebar keeps the REPL session and screen state; `Ctrl+L` clears the REPL
screen.

Vixl edits cells as strings; Parquet saves currently write string columns.
HDF5 read/write uses an embedded Python bridge and the vixl-managed PyTables
runtime installed under `~/.vixl/hdf`. The Python REPL uses
`VIXL_REPL_PYTHON` when set, then `VIXL_HDF_PYTHON`, then the vixl-managed
runtime, then `python3`/`python`.

## Keys

- `h` / `j` / `k` / `l` - move
- `H` / `L` - previous/next sheet
- `i` / `Enter` - edit the focused cell
- `x` - clear the focused cell
- `Ctrl+S` - save
- `Ctrl+T` - save and quit
- `:w [path]` - save, optionally to a new path
- `,ira` / `,irb` - insert row above/below
- `,dr` - delete row
- `,ica` / `,icb` - insert column left/right
- `,dc` - delete column
- `,rnc` - rename current column
- `,rns` - rename current sheet
- `,repl` - toggle right-side Python REPL
- `Ctrl+L` in REPL - clear REPL screen
- `,ns` - add a new sheet
- `,xar` - expand/collapse all rows
- `>` / `<` - widen or narrow the focused column by 1 character
- `?` - help
- `q` - quit

## Development

```bash
go test ./...
go run ./cmd/vixl help
```

Tagged release builds stamp `internal/version.Version` into the shipped binary.
