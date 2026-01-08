import io
import sys
import numpy as np


class CommandExecutor:
    def __init__(self, app_state):
        self.state = app_state

    def execute(self, code):
        stdout = io.StringIO()
        stderr = io.StringIO()
        env = {
            'df': self.state.df,
            'np': np,
        }
        try:
            old_out, old_err = sys.stdout, sys.stderr
            sys.stdout, sys.stderr = stdout, stderr
            exec(code, env, env)
            self.state.df = env.get('df', self.state.df)
        except Exception as e:
            stderr.write(str(e))
        finally:
            sys.stdout, sys.stderr = old_out, old_err
        out_lines = stdout.getvalue().splitlines() + stderr.getvalue().splitlines()
        return out_lines