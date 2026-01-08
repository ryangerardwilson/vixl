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
        import ast
        old_out, old_err = sys.stdout, sys.stderr
        try:
            sys.stdout, sys.stderr = stdout, stderr

            parsed = ast.parse(code)
            last_value = None

            if parsed.body and isinstance(parsed.body[-1], ast.Expr):
                expr = ast.Expression(parsed.body.pop().value)
                exec(compile(parsed, '<exec>', 'exec'), env, env)
                last_value = eval(compile(expr, '<eval>', 'eval'), env, env)
            else:
                exec(code, env, env)

            if last_value is not None:
                print(last_value)

            self.state.df = env.get('df', self.state.df)
        except Exception as e:
            stderr.write(str(e))
        finally:
            sys.stdout, sys.stderr = old_out, old_err
        out_lines = stdout.getvalue().splitlines() + stderr.getvalue().splitlines()
        return out_lines