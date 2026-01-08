import curses
from screen_renderer import ScreenRenderer
from grid_model import GridModel


class Orchestrator:
    """
    Traffic controller for v0.
    Owns the main loop and coordinates state and rendering.
    """

    def __init__(self, stdscr, state):
        self.stdscr = stdscr
        self.state = state
        self.renderer = ScreenRenderer(stdscr)
        self.grid = GridModel(state)

    def run(self):
        stdscr = self.stdscr
        # Load data (v0: single file from argv)
        import sys
        if len(sys.argv) < 2:
            stdscr.addstr(0, 0, "Usage: v0/main.py <file.csv or file.parquet>")
            stdscr.refresh()
            stdscr.getch()
            return

        self.grid.load(sys.argv[1])

        # Basic event loop with navigation (v0)
        curses.curs_set(0)
        while True:
            self.renderer.draw(self.state)
            key = stdscr.getch()

            # Global keys
            if key == 19:  # Ctrl+S save
                try:
                    self.grid.save()
                    self.state.command_output = 'Saved'
                except Exception as e:
                    self.state.command_output = f"Error: {e}"
                continue

            if key == 20:  # Ctrl+T save and exit
                try:
                    self.grid.save()
                except Exception:
                    pass
                break
            if key == 24 and self.state.mode == 'normal':  # Ctrl+X
                break

            if key == 12:  # Ctrl+L clears command output
                self.state.command_output = None
                continue

            if key == 27:  # ESC
                self.state.mode = 'normal'
                continue

            # Mode switch
            if self.state.mode == 'normal' and key == ord(':'):
                self.state.mode = 'command'
                self.state.command_buffer = ''
                continue

            # NORMAL mode
            if self.state.mode == 'normal' and key == ord('?'):
                self.state.command_output = (
                    "NORMAL MODE\n"
                    "  h j k l   Move\n"
                    "  :         Command mode\n"
                    "  x         Quit\n"
                    "  ?         Help\n\n"
                    "COMMAND MODE\n"
                    "  :w        Save\n"
                    "  :wq       Save & quit\n"
                    "  Ctrl+S    Save\n"
                    "  Ctrl+T    Save & quit\n"
                    "  Ctrl+L    Clear output\n"
                    "  Esc       Normal mode"
                )
                continue

            # NORMAL mode
            if self.state.mode == 'normal' and key == ord('.'):
                self.state.show_all_rows = not self.state.show_all_rows
                self.state.voffset = 0
                continue

            if self.state.mode == 'normal':
                # Cell-wise navigation
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
                elif key == ord('j'):
                    if not self.state.show_all_rows and self.state.rows > 20:
                        # top block
                        if self.state.curr_row < 4:
                            self.state.curr_row += 1
                        # jump over ellipsis
                        elif self.state.curr_row == 4:
                            self.state.curr_row = self.state.rows - 5
                        # bottom block
                        elif self.state.curr_row < self.state.rows - 1:
                            self.state.curr_row += 1
                    elif self.state.curr_row < self.state.rows - 1:
                        self.state.curr_row += 1
                    self.state.highlight_mode = 'cell'
                elif key == ord('k'):
                    if not self.state.show_all_rows and self.state.rows > 20:
                        # bottom block
                        if self.state.curr_row > self.state.rows - 5:
                            self.state.curr_row -= 1
                        # jump over ellipsis
                        elif self.state.curr_row == self.state.rows - 5:
                            self.state.curr_row = 4
                        # top block
                        elif self.state.curr_row > 0:
                            self.state.curr_row -= 1
                    elif self.state.curr_row > 0:
                        self.state.curr_row -= 1
                    self.state.highlight_mode = 'cell'

                # Row-wise navigation (capital J/K)
                elif key == ord('J') and self.state.curr_row < self.state.rows - 1:
                    self.state.curr_row += 1
                    self.state.voffset += 1
                    self.state.highlight_mode = 'row'
                elif key == ord('K') and self.state.curr_row > 0:
                    self.state.curr_row -= 1
                    self.state.voffset = max(0, self.state.voffset - 1)
                    self.state.highlight_mode = 'row'

                # Column-wise navigation (capital H/L)
                elif key == ord('H') and self.state.curr_col > 0:
                    self.state.curr_col -= 1
                    self.state.col_offset = max(0, self.state.curr_col)
                    self.state.highlight_mode = 'column'
                elif key == ord('L') and self.state.curr_col < self.state.cols - 1:
                    self.state.curr_col += 1
                    self.state.col_offset = max(0, self.state.curr_col)
                    self.state.highlight_mode = 'column'

            # COMMAND mode (input only for now)
            elif self.state.mode == 'command':
                if key in (10, 13):  # Enter -> execute
                    code = self.state.command_buffer.strip()

                    # Built-in commands
                    if code == 'w':
                        try:
                            self.grid.save()
                            self.state.command_output = 'Saved'
                        except Exception as e:
                            self.state.command_output = f"Error: {e}"
                        self.state.command_buffer = ''
                        self.state.mode = 'normal'
                        continue

                    if code == 'wq':
                        try:
                            self.grid.save()
                        except Exception:
                            pass
                        break
                    import numpy as np
                    import time
                    code = self.state.command_buffer.strip()
                    import io
                    from contextlib import redirect_stdout
                    try:
                        buf = io.StringIO()
                        with redirect_stdout(buf):
                            # Try eval first
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
                            self.state.command_output = output.rstrip() if output else "Executed"
                        except Exception as e:
                            self.state.status_message = f"Error: {e}"
                            self.state.status_message_until = time.time() + 3
                    except Exception as e:
                        self.state.status_message = f"Error: {e}"
                        self.state.status_message_until = time.time() + 3

                    self.state.command_buffer = ''
                    self.state.mode = 'normal'
                elif key == curses.KEY_BACKSPACE or key == 127:
                    self.state.command_buffer = self.state.command_buffer[:-1]
                elif 32 <= key <= 126:
                    self.state.command_buffer += chr(key)
