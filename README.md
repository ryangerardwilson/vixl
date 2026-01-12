# Vixl

Vixl is a **Vim-first, terminal-native spreadsheet editor** for fast, explicit
manipulation of tabular data using Pandas and NumPy.

It is designed for users who prefer keyboard-driven workflows and want full
transparency over how their data is transformed.

---

## Running the App

Run the application via the root entrypoint:

```bash
python main.py <csv-or-parquet-file>
```

- CSV and Parquet files are supported
- If the file does not exist, a blank file is created automatically

### Bash completion (auto-provisioned, warning-only)
- On first run, Vixl creates `~/.config/vixl/completions/vixl.bash`.
- Add this block to your `~/.bashrc` (or `~/.bash_profile` if you do not have a `.bashrc`):
  ```bash
  # >>> vixl bash completion >>>
  if [ -f "$HOME/.config/vixl/completions/vixl.bash" ]; then
      source "$HOME/.config/vixl/completions/vixl.bash"
  fi
  # <<< vixl bash completion <<<
  ```
- Then reload your shell (or run `source ~/.bashrc`).
- If completion is not detected, Vixl prints a warning and continues to launch. To silence the warning without enabling completion, set `VIXL_SKIP_COMPLETION_CHECK=1` in your environment.
- Behavior: after activation, **only** `vixl <TAB>` is completed; `python main.py` is intentionally not hooked to avoid interfering with ordinary Python. Completions suggest only `.csv` and `.parquet` files for the first argument; directories are still offered so you can descend paths. Dotfiles and dot-directories are hidden unless you start the path with a leading `.`; `__pycache__/` is also hidden unless you explicitly type that prefix.
- For a friendly command name, create a symlink in a PATH directory (and make `main.py` executable if needed), e.g.: `ln -s "$PWD/main.py" "$HOME/.local/bin/vixl"` (or set an alias `alias vixl='python /path/to/main.py'`). Completion covers the `vixl` command once the bashrc block is sourced.

---

## Features

- Vim-style modal navigation
- Command-driven DataFrame mutation
- Pandas (`pd`) and NumPy (`np`) preloaded in execution context
- Safe handling of empty tables
- Content-aware, auto-sized columns
- Right-aligned cell rendering
### Vixl – interactive DataFrame editor (curses)
- Single-line command bar at the bottom.
- Modal overlays for output and shortcuts (content-sized, up to 50% of terminal height).
- Extensions loaded from `~/.config/vixl/extensions`, namespaced under `df.vixl` to avoid pandas collisions.
- Persistent history at `~/.config/vixl/history.log`.

### Quick start
- No argument: `python main.py`
  Starts with an unsaved default DataFrame (columns `col_a`, `col_b`, `col_c`, 3 empty rows). You must Save/Save-As to persist.
- With file: `python main.py <file.csv|file.parquet>`
  Loads or creates the file; auto-detects CSV/Parquet.

### Saving / Save-As
- Ctrl+S: Save. If the file is unknown, a single-line “Save as:” prompt appears in the bottom strip. Enter path (must be .csv or .parquet); overwrites without extra confirmation. Esc cancels.
- Ctrl+T: Save & exit. If unsaved, uses the same prompt; exits only after a successful save.
- Status messages: “Saved <path>”, “Save failed: …”, “Save canceled”, “Path required”, “Save failed: use .csv or .parquet”.

### Layout & panes
- Table view for the DataFrame.
- Shared bottom strip for status/command/Save-As prompt.
- Overlays (output or shortcuts) appear centered, resize to content up to 50% of terminal height.

### Command bar (single-line)
- Enter: `:` (from df focus)
- Execute: Enter
- Cancel: Esc
- History: Ctrl+P / Ctrl+N (Ctrl+N past newest clears)
- Edit/navigation keys: Left/Right/Home/End, Backspace; Emacs-style: Alt+F / Alt+B (word fwd/back), Ctrl+W (delete word backward), Ctrl+U (kill to line start), Ctrl+H / Ctrl+D (move left/right), Ctrl+A / Ctrl+E (line start/end)

> Note: Vixl is vi-first for grid navigation, but the command bar deliberately uses Emacs-style editing keys. In a single-line, insert-first, REPL-like input (like a terminal), Emacs word-motion/kill bindings provide faster, lower-friction text editing than modal vi navigation, so they are enabled here.

### Output modal
- Appears only when there is output from a command.
- Close: Esc / q / Enter; Scroll: j / k

### Shortcuts modal
- `?` (from df) opens the shortcuts list.
- Close: Esc / q / Enter; Scroll: j / k

### DF navigation & editing (df normal)
- Numeric prefixes (counts) supported for: h/j/k/l, Ctrl+J/K/H/L, ,ira / ,irb, ,dr, ,+rl / ,-rl; in cell_normal: h/l and w/b
- Repeat last change: `.` (mutations only; excludes column insert/rename/delete and command bar commands)
- Undo / Redo: `u` / `r`
- Move: h / j / k / l
- Big jumps: Ctrl+J / Ctrl+K (~5% rows down/up), Ctrl+H / Ctrl+L (~20% cols left/right)
- Row expansion (leader): `,xr` expands/collapses the current row; `,xar` expands/collapses all rows; `,xc` collapses all expansions. Expanded rows wrap vertically on word boundaries (hard-break only for overlong words) within existing column widths.
- Open command: `:`; `n` enters cell_normal on current cell (leader sequences show in the status bar as you type)
- Edit cell: `i` (preload value), or `, e` (preload), or `, c c` (empty buffer). When the current row is expanded (via `,xr`/`,xar`), `i` and `, e` open the external editor instead of inline insert.
- External edit current cell: `, v` launches your `$VISUAL`/`$EDITOR` (via Alacritty if available); status shows "Receiving new data from editor" while syncing; returns to cell_normal at the cell start.
- Clear cell: `x` (in df mode)
- Insert rows: `, i r a` (insert above), `, i r b` (insert below); Delete row: `, d r`
- Column ops: `, i c a` (insert col after), `, i c b` (insert col before), `, d c` (delete col), `, r n c` (rename col). Insert prompts for name + dtype (object, Int64, float64, boolean, datetime64[ns]).
- Go to edges: `, h` (first col), `, l` (last col), `, k` (first row), `, j` (last row)
- Adjust row lines (height): `,+rl` (increase), `,-rl` (decrease, min 1)
- Copy df to clipboard (TSV): `, y` (uses `wl-copy`, paste-friendly for Sheets/Excel)
- `?` opens shortcuts


### Cell edit modes
- `cell_insert`: type to edit; Backspace deletes; Esc commits to `cell_normal`.
- `cell_normal`: h / l moves within buffer; 0 / $ jump to line edges; w / b move by word; `, e` / `, c c` / `, d c` / `, n r`; `, v` opens the external editor for the current cell and returns with the cursor at the start; `i` enters insert; Esc returns to df normal.

### History
- Stored at `~/.config/vixl/history.log`.
- Command bar history navigation: Ctrl+P / Ctrl+N.

### Extensions
- Location: `~/.config/vixl/extensions/*.py`
- Loaded at startup; functions are exposed under `df.vixl.<name>` to avoid pandas attribute collisions.
- Mutation contract:
  - Explicit commit required for extension calls: return `(df, True)`, or set `commit_df = True` and assign `df = new_df`. Without this, changes from extension calls are discarded.
  - Natural commands (no extension calls) auto-commit the sandboxed `df`.
- Config: `~/.config/vixl/config.json` (JSON-only). Supported keys:
  - `AUTO_COMMIT` (bool, default False)
  - `cmd_mode.tab_fuzzy_expansions_register` (list of strings) for cmd-mode Tab insertions.
  Example:
  ```json
  {
    "AUTO_COMMIT": false,
    "cmd_mode": {
      "tab_fuzzy_expansions_register": [
        "df.vixl.distribution_ascii_bar(bins=10)",
        "df.pivot()",
        "df.info()"
      ]
    }
  }
  ```
- Examples (save under `~/.config/vixl/extensions/`):
   1) multiply_cols (explicit commit)
      ```python

     def multiply_cols(df, col_a, col_b, out_col="product"):
         df[out_col] = df[col_a] * df[col_b]
         return df, True
     ```
  2) add_ratio (commit flag or tuple)
     ```python
     def add_ratio(df, num_col, den_col, out_col="ratio"):
         df[out_col] = df[num_col] / df[den_col]
         commit_df = True  # honored if you set it and assign df; or return (df, True)
         return df, True
     ```
  3) top_n (read-only, no commit)
     ```python
     def top_n(df, col, n=5):
         return df.sort_values(col, ascending=False).head(n)
     ```
  4) ascii_bar (fun display; no commit)
     ```python
     def ascii_bar(df, col, width=40):
         vals = df[col].fillna(0)
         maxv = vals.max() if len(vals) else 0
         lines = []
         for v in vals:
             bar_len = 0 if maxv == 0 else int(width * (v / maxv))
             lines.append("|" + "█" * bar_len)
         return "\n".join(lines)
     ```
     Usage: `df.vixl.ascii_bar("col_a")` → shows a simple bar chart in the output modal.
  5) normalize_cols (explicit commit)
     ```python
     def normalize_cols(df, cols, prefix="norm_"):
         for c in cols:
             mx = df[c].max()
             mn = df[c].min()
             df[f"{prefix}{c}"] = (df[c] - mn) / (mx - mn) if mx != mn else 0
         return df, True
     ```
- Usage examples in cmd:
  - `df.vixl.multiply_cols("col_a", "col_b", out_col="prod")` (commits via tuple)
  - `df.vixl.top_n("col_a", 3)` (read-only; output modal)
  - `df.vixl.ascii_bar("col_a")` (bar graph in modal)

### Removed / changed features
- Leader commands (`,ya`, `,yap`, `,yio`, `,o`, `,df`) removed.
- Multi-line command pane removed; output pane is no longer side-by-side—now modal only.
- Explicit save and save-on-exit

### df Mode: Normal vs Insert

In **df mode**, interaction is strictly modal and scoped to the grid:

- **df Normal mode** is used for navigation and selection only. It never mutates data.
- **df Insert mode** never edits the grid. Instead, it generates a context-aware Pandas mutation command and opens it in the command pane.

For example, pressing `i` on a cell pre-fills a command such as:

```python
df.iloc[row, col] = value
```

Users edit and execute the command explicitly in **command pane Insert mode**.
The grid is a navigation and visualization surface, never a text editor.

---

## Code Layout

The repository reflects the current, runnable implementation of Vixl.

All Python files live in the project root:

- `main.py` – application entrypoint and bootstrap
- `orchestrator.py` – main event loop and coordination
- `app_state.py` – core application state and invariants
- `file_type_handler.py` – file loading and saving logic
- `command_executor.py` – command execution sandbox
- `grid_pane.py`, `command_pane.py`, `output_pane.py` – UI panes

Each file represents a clear product responsibility, with one primary class per
file.

---

## Philosophy

- Terminal-native, curses-based UI
- Vim-inspired modal interaction
- Explicit, inspectable data manipulation
- Dense, information-first rendering
- Minimal hidden behavior

For a detailed description of scope and constraints, see `ProjectScope.md`.
