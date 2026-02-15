Start by reading the README.md, PROJECTSCOPE.md, CHANGELOG.md, and knowing that
main.py is the entry point.

Component responsibilities (1-2 lines each):
- main.py: CLI entrypoint; parses args, handles upgrade/version/help, and boots the loading screen + orchestrator.
- orchestrator.py: Main event loop/controller; routes input, coordinates panes/overlays/prompts, and drives render + command execution.
- app_state.py: Central mutable app state and invariants (df, file info, expansion state, undo/redo).
- file_type_handler.py: Load/save CSV/Parquet files with validation and default DataFrame creation.
- default_df_initializer.py: Create the default seed DataFrame (col_a/col_b/col_c + initial rows).
- loading_screen.py: Animated loading screen that runs the loader and gates startup until data is ready.
- ascii_art.py: Stores the ASCII logo art used by the loading screen.
- screen_layout.py: Computes curses window layout for table, status/command strip, and overlays.
- grid_pane.py: Renders the DataFrame grid and maintains cursor/viewport/highlight state.
- command_pane.py: Command bar buffer editing, history navigation, and inline completion suggestions.
- column_prompt.py: Column insert/rename prompt flow plus dtype validation and application.
- save_prompt.py: Save-as prompt input and save/save-exit flow.
- overlay.py: Modal overlay rendering for output/help and scroll handling.
- shortcut_help_handler.py: Supplies the help/shortcuts text lines.
- pagination.py: Row paging logic for large DataFrames.
- command_executor.py: Sandboxed command execution and config loading.
- completions_handler.py: Generates bash completion script and prints activation instructions.
- history_manager.py: Loads, appends, and persists command history to disk.
- config_paths.py: Defines config paths and loads config defaults.
- df_editor.py: Composes DF editor subsystems and exposes editing operations to the orchestrator.
- df_editor_context.py: Shared context container for DF editor subsystems.
- df_editor_counts.py: Tracks numeric prefix counts for DF-mode commands.
- df_editor_undo.py: Manages undo/redo stacks and last-action metadata.
- df_editor_df_ops.py: Performs row/column operations and row-expansion toggles.
- df_editor_df_mode.py: Handles DF-normal keybindings, movement, and editing actions.
- df_editor_external.py: External editor workflows (vim edits, visual fill, config edit, JSON preview).
- df_editor_visual.py: Visual selection state and syncing to the grid.
- cell_coercion.py: Coerces text input into typed cell values.
- .github/scripts/find-python-url.py: Release helper to locate Python download URLs for builds.
