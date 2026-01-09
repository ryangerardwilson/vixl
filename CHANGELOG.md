# Changelog

## [Unreleased]
- Ongoing improvements and refinements.

## 2026-01-09

### Added
- Persistent global command history stored at `~/.vixl_history`.
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
