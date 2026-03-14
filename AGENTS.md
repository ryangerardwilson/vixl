# Vixl Agent Guide

## Workspace Defaults
- Follow `/home/ryan/Documents/agent_context/CLI_TUI_STYLE_GUIDE.md` for CLI/TUI taste and help shape.
- Follow `/home/ryan/Documents/agent_context/CANONICAL_REFERENCE_IMPLEMENTATION_FOR_CLI_AND_TUI_APPS.md` for executable contract details such as `-h`, `-v`, `-u`, installer behavior, release workflow expectations, and regression expectations.
- This file only records `vixl`-specific constraints or durable deviations.

This file is optimized for coding agents working in this repo.

## Start Here (in order)
1. Read `README.md` for user-facing behavior.
2. Read `PROJECTSCOPE.md` for intended architecture and non-goals.
3. Read `CHANGELOG.md` for recent behavior shifts.
4. Treat `main.py` as the runtime entrypoint.
5. Verify behavior in code when docs conflict.

## Fast Reality Check (important)
Some docs lag implementation. Confirm in code before changing behavior.

Current known mismatches to watch:
- `command_pane.py` does not provide tab completion (history/editing only).
- The old `output_pane.py` reference in `README.md` is stale; overlays are handled by `overlay.py`.
- Command execution is in-process (`command_executor.py`), not external command registration.

## Runtime Architecture
- Flow: `main.py` -> `loading_screen.py` -> `orchestrator.py`.
- `orchestrator.py` owns the event loop, focus switching, render calls, save flow, command execution wiring, and history persistence.
- `df_editor.py` composes editing subsystems and is the integration surface for DF-mode key handling.

## Canonical Components (what to open first)
- `main.py`: CLI entrypoint (`-h`, `-v`, `-u`), file/bootstrap setup, curses startup.
- `orchestrator.py`: Main controller loop and UI coordination.
- `app_state.py`: Central mutable state (`df`, sheets, undo/redo stacks, row expansion invariants).
- `command_executor.py`: Python sandbox execution, df commit semantics.
- `df_editor.py`: Facade composing DF editing modules.

Subsystems under the DF editor:
- `df_editor_context.py`: shared context object.
- `df_editor_counts.py`: numeric prefix count state.
- `df_editor_undo.py`: undo/redo snapshots and metadata.
- `df_editor_df_ops.py`: row/column operations and expansion helpers.
- `df_editor_df_mode.py`: DF-normal key handling and leader sequence behavior.
- `df_editor_external.py`: Vim-based edit workflows (`i`, visual fill, config edit, JSON preview).
- `df_editor_visual.py`: visual block selection state.

UI and prompt modules:
- `grid_pane.py`: DataFrame rendering, cursor/viewport, highlight/visual plumbing.
- `command_pane.py`: command line editing + history navigation.
- `save_prompt.py`: save-as prompt and save/exit flow.
- `column_prompt.py`: insert/rename column prompt + dtype validation.
- `overlay.py`: modal output/help rendering and scroll state.
- `screen_layout.py`: curses window layout math.
- `shortcut_help_handler.py`: shortcut/help text source.

I/O and config:
- `file_type_handler.py`: CSV/Parquet/XLSX/HDF5 load/save logic.
- `default_df_initializer.py`: seeded default DataFrame.
- `history_manager.py`: history load/append/persist.
- `config_paths.py`: config/history paths + config loading.
- `completions_handler.py`: shell completion script generation/installation guidance.
- `.github/scripts/find-python-url.py`: release helper script.

## Behavioral Invariants (preserve these)
- Data model is always a Pandas DataFrame (`app_state.py`).
- If there are columns, table must remain render-safe with at least one row.
- Command execution only commits DataFrame changes when:
  - code assigns to `df`, or
  - result is `(df, True)`, or
  - `commit_df = True` is set with DataFrame in `df`.
- Command failures must not mutate app state.
- Grid editing is Vim-based (`i`); inline insert mode is removed.
- Visual mode operations (`v`, `d`, `i` bulk fill) must remain rectangular-selection based.

## Common Change Paths
- Keybinding behavior: start in `df_editor_df_mode.py`, then check `orchestrator.py` focus/dispatch.
- Grid rendering/selection issues: inspect `grid_pane.py` and `df_editor_visual.py` together.
- Save/load bugs: inspect `file_type_handler.py`, `save_prompt.py`, and `orchestrator._save_df`.
- Command execution semantics: `command_executor.py` + command history wiring in `orchestrator.py`.
- Sheet navigation behavior: `app_state.py` + `DfEditor.switch_sheet`.

## Testing Workflow
- Run all tests: `pytest -q`
- Run targeted tests by file, for example:
  - `pytest -q test_main.py`
  - `pytest -q test_df_editor_rows.py`
  - `pytest -q test_df_editor_external_edit.py`

When changing key handling, prompts, or editor behavior, run the nearest focused tests first, then the full suite.

## Agent Working Rules for This Repo
- Keep edits minimal and local; avoid broad refactors unless requested.
- Preserve the flat module structure (no new package tree unless explicitly requested).
- Prefer updating behavior where it currently lives instead of adding parallel codepaths.
- Update docs when behavior changes; at minimum adjust `README.md`/`PROJECTSCOPE.md`/`CHANGELOG.md` entries touched by the change.
- If you discover conflicting instructions, follow running code and leave a note in your summary.

## Quick Commands
- Launch app: `python main.py [optional-path]`
- Show help/version: `python main.py -h` / `python main.py -v`
- Run upgrade path logic: `python main.py -u`

## Definition of Done for Agent Changes
- Code change is implemented.
- Relevant tests pass (or failures are explained).
- Any behavior change is documented.
- No stale references introduced (for example, removed modules/features).
