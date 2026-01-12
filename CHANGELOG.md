# Changelog

## [Unreleased]
- Added row expansion: `,xr` toggles expansion of the current row; `,xar` toggles expansion of all rows; `,xc` collapses all expansions. Expanded rows wrap on word boundaries (hard-break only for overlong words) to show full content without widening columns; collapsed default remains single-line. When expanded, `i` and `,e` open the external editor instead of inline insert. Ctrl+L remains the 20% right jump.
- Added external editor workflow on `,v` from both df normal and cell_normal; shows "Receiving new data from editor" while syncing and returns the cursor to the start of the cell on completion.
- Added bash completion auto-provisioning at `~/.config/vixl/completions/vixl.bash` (covers `python main.py`, `python3 main.py`, and `vixl`); startup now warns (does not block) when completion is not detected, with `VIXL_SKIP_COMPLETION_CHECK=1` to suppress the warning; completion logic lives in `completions_handler.py`, and README documents symlink/alias guidance for `vixl`.
- Added df-mode column workflows: `n` to enter cell_normal, `,ica`/`,icb` insert columns (prompt name+dtype), `,dc` delete column, `,rnc` rename column; column prompts share the bottom-strip UX.
- Added no-arg launch with default DataFrame (col_a/col_b/col_c, 3 empty rows) as unsaved buffer.
- Added Save-As prompt (inline bottom strip) for unsaved buffers; Ctrl+S saves; Ctrl+T saves & exits only on success; validates .csv/.parquet.
- Single-line command bar; output as modal overlay; shortcuts modal (`?`); overlays auto-size to content up to 50% of terminal height.
- Command history relocated to `~/.config/vixl/history.log`; command bar history navigation via Ctrl+P/Ctrl+N.
- Extensions: auto-load from `~/.config/vixl/extensions`; exposed under `df.vixl.<name>` to avoid pandas collisions; explicit mutation signaling `(df, True)` or `commit_df=True`; natural commands auto-commit unless an extension was invoked. Configurable `AUTO_COMMIT` via `~/.config/vixl/config.json`.
- Optional config.json at `~/.config/vixl/config.json` to predefine cmd-mode Tab insertions via `cmd_mode.tab_fuzzy_expansions_register`.
- DF-normal shortcut `,y` copies the entire DataFrame as TSV to clipboard via `wl-copy` for Sheets/Excel pasting.
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
