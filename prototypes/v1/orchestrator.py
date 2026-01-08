import curses
import os
import subprocess
import tempfile
from screen_renderer import ScreenRenderer
from grid_model import GridModel


class Orchestrator:
    """
    Traffic controller for v0.
    Owns the main loop and coordinates state and rendering.
    """

    EDITOR_THRESHOLD = 50

    def __init__(self, stdscr, state):
        self.stdscr = stdscr
        self.state = state
        self.renderer = ScreenRenderer(stdscr)
        self.grid = GridModel(state)

    # -----------------------------
    # External editor integration
    # -----------------------------
    def edit_command_external(self, initial_command: str) -> str:
        editor = "vim"

        with tempfile.NamedTemporaryFile(mode="w+", suffix=".py", delete=False) as f:
            f.write(initial_command)
            f.flush()
            path = f.name

        curses.def_prog_mode()
        curses.endwin()
        try:
            subprocess.call([
                editor,
                "-u", os.path.expanduser("~/.vimrc"),
                "+normal!G$A",
                path,
            ])
        finally:
            curses.reset_prog_mode()
            curses.noecho()
            curses.cbreak()
            curses.curs_set(0)
            self.stdscr.keypad(True)
            curses.flushinp()
            self.stdscr.erase()
            self.stdscr.refresh()

        try:
            with open(path, "r") as f:
                edited = f.read().strip()
        finally:
            os.unlink(path)

        return edited

    # -----------------------------
    # Shared command prefill
    # -----------------------------
    def build_docstring_prefill(self) -> str:
        try:
            body = self.state.df.__repr__()
        except Exception:
            body = ''
        return (
            '"""\n'
            + body
            + '\n\n'
            + 'print(df.columns.to_list())\n'
            + 'print(df.dtypes)\n'
            + '"""\n\n'
        )

    # -----------------------------
    # Command mode handler
    # -----------------------------
    def handle_command_mode(self, key):
        import numpy as np
        import io
        from contextlib import redirect_stdout

        if key in (10, 13):  # Enter
            code = self.state.command_buffer.strip()
            error = False

            if code == 'w':
                try:
                    self.grid.save()
                    self.state.command_output = 'Saved'
                except Exception as e:
                    self.state.command_output = f"Error: {e}"
                self.state.command_buffer = ''
                self.state.command_cursor = 0
                self.state.command_scroll = 0
                self.state.mode = 'normal'
                return

            if code == 'wq':
                try:
                    self.grid.save()
                except Exception:
                    pass
                raise SystemExit

            try:
                buf = io.StringIO()
                with redirect_stdout(buf):
                    result = eval(code, {}, {"df": self.state.df, "np": np})
                output = buf.getvalue()
                if output:
                    self.state.command_output = output.rstrip()
                elif result is not None:
                    self.state.command_output = str(result)
            except SyntaxError:
                try:
                    buf = io.StringIO()
                    with redirect_stdout(buf):
                        exec(code, {}, {"df": self.state.df, "np": np})
                    self.grid.refresh_from_df()
                    output = buf.getvalue()
                    self.state.command_output = output.rstrip() if output else 'Executed'
                except Exception as e:
                    error = True
                    self.state.command_output = f"Error: {e}"
            except Exception as e:
                error = True
                self.state.command_output = f"Error: {e}"

            if not error:
                self.state.command_buffer = ''
                self.state.command_cursor = 0
                self.state.command_scroll = 0
                self.state.mode = 'normal'
            return

        if key in (curses.KEY_LEFT, 2):
            self.state.command_cursor = max(0, self.state.command_cursor - 1)
        elif key in (curses.KEY_RIGHT, 6):
            self.state.command_cursor = min(len(self.state.command_buffer), self.state.command_cursor + 1)
        elif key == 1:
            self.state.command_cursor = 0
        elif key == 5:
            self.state.command_cursor = len(self.state.command_buffer)
        elif key in (curses.KEY_BACKSPACE, 127):
            if self.state.command_cursor > 0:
                i = self.state.command_cursor
                self.state.command_buffer = (
                    self.state.command_buffer[:i - 1]
                    + self.state.command_buffer[i:]
                )
                self.state.command_cursor -= 1
        elif 32 <= key <= 126:
            i = self.state.command_cursor
            self.state.command_buffer = (
                self.state.command_buffer[:i]
                + chr(key)
                + self.state.command_buffer[i:]
            )
            self.state.command_cursor += 1

    # -----------------------------
    # Main loop
    # -----------------------------
    def run(self):
        stdscr = self.stdscr
        import sys

        if len(sys.argv) < 2:
            stdscr.addstr(0, 0, "Usage: v0/main.py <file.csv or file.parquet>")
            stdscr.refresh()
            stdscr.getch()
            return

        self.grid.load(sys.argv[1])
        curses.curs_set(0)

        while True:
            self.renderer.draw(self.state)
            key = stdscr.getch()

            if key in (ord('h'), ord('j'), ord('k'), ord('l'), ord('H'), ord('J'), ord('K'), ord('L')):
                self.state.command_output = None

            if key == 19:
                try:
                    self.grid.save()
                    self.state.command_output = 'Saved'
                except Exception as e:
                    self.state.command_output = f"Error: {e}"
                continue

            if key == 20:
                try:
                    self.grid.save()
                except Exception:
                    pass
                break

            if key == 24 and self.state.mode == 'normal':
                break

            if key == 12:
                self.state.command_output = None
                continue

            if key == 27:
                self.state.mode = 'normal'
                continue

            # Command mode ':'
            if self.state.mode == 'normal' and key == ord(':'):
                initial = self.build_docstring_prefill()
                edited = self.edit_command_external(initial)
                if not edited:
                    self.state.mode = 'normal'
                    continue

                code = edited
                if code.lstrip().startswith('"""'):
                    parts = code.split('"""', 2)
                    if len(parts) == 3:
                        code = parts[2]

                self.state.command_buffer = code.strip()
                self.state.command_cursor = len(self.state.command_buffer)
                self.state.command_scroll = 0
                self.state.mode = 'command'
                self.handle_command_mode(10)
                continue

            # Insert alias 'i' with scope-aware mutation prefill
            if self.state.mode == 'normal' and key == ord('i'):
                r = self.state.curr_row
                c = self.state.curr_col
                col = self.state.col_names[c]
                df = self.state.df

                if self.state.highlight_mode == 'cell':
                    snippet = f"df.loc[{r}, '{col}'] = {repr(df.iloc[r, c])}"
                elif self.state.highlight_mode == 'row':
                    snippet = f"df.loc[{r}] = {repr(df.loc[r].to_dict())}"
                else:  # column
                    snippet = f"df = df.rename(columns={{'{col}': '{col}'}})"

                initial = self.build_docstring_prefill() + snippet + "\n"
                edited = self.edit_command_external(initial)
                if not edited:
                    self.state.mode = 'normal'
                    continue

                code = edited
                if code.lstrip().startswith('"""'):
                    parts = code.split('"""', 2)
                    if len(parts) == 3:
                        code = parts[2]

                self.state.command_buffer = code.strip()
                self.state.command_cursor = len(self.state.command_buffer)
                self.state.command_scroll = 0
                self.state.mode = 'command'
                self.handle_command_mode(10)
                continue

            if self.state.mode == 'normal' and key == ord('?'):
                self.state.command_output = (
                    "NORMAL MODE\n"
                    "  h j k l   Move\n"
                    "  :         Command mode\n"
                    "  i         Insert (command prefill)\n"
                    "  .         Toggle row truncation\n"
                    "  ?         Help\n\n"
                    "COMMAND MODE\n"
                    "  Enter     Execute\n"
                    "  Ctrl-A/E  Start/End\n"
                    "  Ctrl-B/F  Left/Right\n"
                    "  Esc       Normal mode"
                )
                continue

            if self.state.mode == 'normal' and key == ord('.'):
                self.state.show_all_rows = not self.state.show_all_rows
                self.state.voffset = 0
                continue

            if self.state.mode == 'normal':
                # Horizontal navigation (always visible)
                if key == ord('h') and self.state.curr_col > 0:
                    self.state.curr_col -= 1
                    if self.state.curr_col < self.state.col_offset:
                        self.state.col_offset = self.state.curr_col
                    self.state.highlight_mode = 'cell'

                elif key == ord('l') and self.state.curr_col < self.state.cols - 1:
                    self.state.curr_col += 1
                    if self.state.curr_col >= self.state.col_offset + 1:
                        self.state.col_offset = max(0, self.state.curr_col - 1)
                    self.state.highlight_mode = 'cell'

                # Vertical navigation (skip hidden rows)
                elif key in (ord('j'), ord('J')):
                    if not self.state.show_all_rows and self.state.rows > 20:
                        if self.state.curr_row < 4:
                            self.state.curr_row += 1
                        elif self.state.curr_row == 4:
                            self.state.curr_row = self.state.rows - 5
                        elif self.state.curr_row < self.state.rows - 1:
                            self.state.curr_row += 1
                    elif self.state.curr_row < self.state.rows - 1:
                        self.state.curr_row += 1
                    self.state.highlight_mode = 'row' if key == ord('J') else 'cell'

                elif key in (ord('k'), ord('K')):
                    if not self.state.show_all_rows and self.state.rows > 20:
                        if self.state.curr_row > self.state.rows - 5:
                            self.state.curr_row -= 1
                        elif self.state.curr_row == self.state.rows - 5:
                            self.state.curr_row = 4
                        elif self.state.curr_row > 0:
                            self.state.curr_row -= 1
                    elif self.state.curr_row > 0:
                        self.state.curr_row -= 1
                    self.state.highlight_mode = 'row' if key == ord('K') else 'cell'

                # Column-wise jumps
                elif key == ord('H') and self.state.curr_col > 0:
                    self.state.curr_col -= 1
                    self.state.col_offset = max(0, self.state.curr_col)
                    self.state.highlight_mode = 'column'

                elif key == ord('L') and self.state.curr_col < self.state.cols - 1:
                    self.state.curr_col += 1
                    self.state.col_offset = max(0, self.state.curr_col)
                    self.state.highlight_mode = 'column'

            elif self.state.mode == 'command':
                self.handle_command_mode(key)
