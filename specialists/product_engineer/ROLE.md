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
- The stable Go data path is CSV/TSV.
- `vixl open` starts an unsaved seeded workbook.
- `vixl open <path>` loads or creates a CSV/TSV file.
- `vixl config` opens the real user config in `$VISUAL`, then `$EDITOR`, then `vim`.
- `help`, `version`, `upgrade`, and `config` must stay fast and free of TUI startup.
- Release artifacts are Linux x64 Go binaries installed by `install.sh`.

## Current Modules

- `cmd/vixl/` - executable entrypoint
- `internal/cli/` - command dispatch and config/upgrade handoff
- `internal/app/` - Bubble Tea grid UI
- `internal/sheet/` - CSV/TSV load, save, and mutation invariants
- `internal/config/` - user config path
- `internal/version/` - stamped release version

## Testing Workflow

- Run all tests with `go test ./...`.
- Keep tests focused on command dispatch, file load/save, installer behavior, and grid mutation invariants.
