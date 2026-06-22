# Changelog

## Go Runtime

- Ported Vixl from a Python terminal app to a Go/Bubble Tea binary.
- Kept the `vixl open [path]`, `vixl config`, `vixl help`, `vixl version`, and
  `vixl upgrade` command surface.
- Narrowed the stable file format to CSV/TSV for the Go runtime.
- Replaced the old source-bundle release path with a Go binary release.
- Added Parquet and XLSX load/save support, read-only XLS import support, and
  file-backed column-width persistence for Parquet/XLSX.
- Restored `,xar` to expand/collapse all rows with wrapped cell rendering.
- Added explicit `.h5`/`.hdf`/`.hdf5` handling that reports the missing HDF5
  runtime strategy instead of treating those extensions as unknown.
- Added multi-sheet XLSX load/save preservation and `H`/`L` sheet navigation.
- Added content-fit default column widths so short columns render compactly
  until customized with `>` or `<`.
- Added multi-sheet Parquet persistence through Vixl workbook metadata
  `vixl.workbook.v1` while keeping single-sheet Parquet as a normal table.
- Added HDF5 read/write through an embedded PyTables bridge and installer-
  managed runtime under `~/.vixl/hdf`.
- Added compact bottom sheet indicators for workbook-capable formats and `,ns`
  to create a new sheet while keeping CSV/TSV single-table only.
- Added transient notification rows above the sheet indicator and a `,rns`
  modal to rename the active sheet in workbook-capable files.
- Added a blinking block cursor for TUI states that collect typed input.
- Added `,repl` to toggle a right-side Python REPL with the active sheet
  loaded into `df` and numpy/pandas preloaded.
- Refined the REPL sidebar so hiding it preserves session state, startup
  chatter stays hidden, the prompt follows output like a terminal, and
  `Ctrl+L` clears the REPL screen.
