# Vixl

Vixl is a Vim-first terminal spreadsheet editor written in Go with a Bubble Tea
TUI. The Go runtime supports CSV and TSV workbooks.

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
vixl config
vixl help
vixl version
vixl upgrade
```

`vixl open` starts an unsaved workbook seeded with `col_a`, `col_b`, and
`col_c`. `vixl open data.csv` loads or creates a CSV/TSV file.

## Keys

- `h` / `j` / `k` / `l` - move
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
- `?` - help
- `q` - quit

## Development

```bash
go test ./...
go run ./cmd/vixl help
```

Tagged release builds stamp `internal/version.Version` into the shipped binary.
