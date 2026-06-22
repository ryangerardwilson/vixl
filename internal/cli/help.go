package cli

const HelpText = `vixl
terminal spreadsheet editor

global actions:
  vixl help
    show this help
  vixl version
    print the installed version
  vixl upgrade
    upgrade to the latest release
  vixl config
    open the config in $VISUAL/$EDITOR

features:
  open the spreadsheet editor on a new sheet or an existing path
  # vixl open [path]
  vixl open
  vixl open data.csv
  vixl open data.parquet
  vixl open data.xlsx
  vixl open data.h5
  vixl open data.xls

  edit command history, clipboard integration, and other local settings
  # vixl config
  vixl config

notes:
  H/L moves between sheets in XLSX, HDF5, and Vixl workbook Parquet files
  ,ns creates a new sheet in workbook-capable files
  ,rns opens a modal to rename the current sheet in workbook-capable files
  ,repl toggles a Python REPL with df, numpy as np, and pandas as pd
  Ctrl+L inside the REPL clears its screen without resetting the session
  .xls opens as a read-only import; save as .xlsx, .parquet, or .h5
  HDF5 uses the installer-managed PyTables runtime under ~/.vixl/hdf
`
