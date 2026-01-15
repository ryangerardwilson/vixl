# Changelog

## [Unreleased]
- Renamed cmd-mode `tab_fuzzy_expansions_register` to `expression_register`; Tab completion is prefix-only against that register.
- Added `:%fz/<query>` and `:%fz#/<query>` to fuzzy-load expression register entries (phrase-aware). Trailing `# comments` and `%fz#/` tags participate in fuzzy search; comment-only matches never insert text. Successful `%fz` loads are now written to command history so they can be recalled via Ctrl+P/Ctrl+N.
- Added DF visual mode: `v` toggles a rectangular selection, Esc exits; `d` clears all selected cells and `i` bulk-fills the selection via Vim (single external edit). Visual selections render inline and the status bar shows `VISUAL` when active.
- Added row expansion: `,xr` toggles expansion of the current row; `,xar` toggles expansion of all rows; `,xc` collapses all expansions. Expanded rows wrap on word boundaries (hard-break only for overlong words) to show full content without widening columns; collapsed default remains single-line.
- Simplified editing: removed `cell_insert`/`cell_normal` modes and the `n`, `,e`, `,v`, `,c c` workflows. Pressing `i` now suspends curses, opens **vim** in the current terminal with the cell value, and commits on exit status 0 (non-zero cancels). External editing is synchronous—no background polling or Alacritty dependency.
- Updated df-mode column workflows: `,ica`/`,icb` insert columns (prompt name+dtype), `,dc` delete column, `,rnc` rename column; column prompts share the bottom-strip UX.
- DF-normal JSON preview: `,pj` opens the current cell as pretty JSON in Vim (read-only flags) in the current terminal session.
- Added a curl-installable Linux x86_64 binary (PyInstaller build) and documented the installer.
- Release workflow now builds inside manylinux2014 via Docker, bundles NumPy/Pandas/PyArrow assets correctly, and uploads `vixl-linux-x64.tar.gz` on each tag.
- `install.sh` auto-detects the latest release, handles version pinning, and adds `~/.vixl/bin` to PATH (unless suppressed).
- Hybrid command execution: pure builtins/df/pd/np commands execute locally, while commands with imports, `df.vixl.*`, escape-hatch names, or other globals run remotely inside the configured `python_path` interpreter. Output and commit semantics are identical between both paths.
- Extensions now live in a single `$XDG_CONFIG_HOME/vixl/extensions.py` file; the legacy `extensions/*.py` layout is deprecated.

- Removed leader commands and multi-line command pane; output pane no longer side-by-side (modal-only output).
- Exit keys (Ctrl+C/Ctrl+X) now work even when overlays are open.


## 2026-01-09

### Added
- Persistent global command history stored at `~/.config/vixl/history.log`.
- CSV and Parquet file support with automatic file creation.
- Pandas (`pd`) and NumPy (`np`) preloaded in the command execution context.

### Changed
- Formalized df Normal mode vs df Insert mode semantics.
- Clarified distinction between df Insert mode and command pane Insert mode.
- df Insert mode strictly pre-fills Pandas mutation commands; the grid never acts as a text editor.
- DataFrame grid display now uses content-aware column widths, capped at 20 characters.
- All grid cells and column headers are right-aligned for improved readability.
- Command history navigation (`Ctrl-P` / `Ctrl-N`) now treats the history file as the single source of truth.
- Project documentation updated to reflect the current, versionless state of the codebase.

### Fixed
- Prevented crashes when opening DataFrames with columns but no rows by enforcing a safe empty-row invariant.
- Disabled leader key handling during command insert mode to allow literal commas and normal text entry.

### Notes
- Prototype and versioned directories have been removed.
- The project documentation now describes the current implementation without version qualifiers.
