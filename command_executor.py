import ast
import builtins
import io
import sys

import numpy as np
import pandas as pd

from config_paths import ensure_config_dirs, load_config

_SAFE_BUILTINS = {
    name: getattr(builtins, name)
    for name in [
        "len",
        "range",
        "min",
        "max",
        "sum",
        "sorted",
        "list",
        "dict",
        "set",
        "tuple",
        "enumerate",
        "zip",
        "abs",
        "all",
        "any",
        "bool",
        "float",
        "int",
        "str",
        "print",
    ]
}
class CommandExecutor:
    def __init__(self, app_state):
        self.state = app_state
        self.startup_warnings = []
        ensure_config_dirs()
        self.config, ignored_cmds = self._load_config_data()


    # ---------- config / warnings ----------
    def _load_config_data(self):
        cfg = load_config()
        return cfg, []

    def reload_config(self):
        self.config, _ = self._load_config_data()
        self.startup_warnings = []
        return []

    # ---------- AST helpers ----------
    def _roots_at_df(self, node):
        cur = node
        while True:
            if isinstance(cur, ast.Name):
                return cur.id == "df"
            if isinstance(cur, ast.Attribute):
                cur = cur.value
                continue
            if isinstance(cur, ast.Subscript):
                cur = cur.value
                continue
            return False

    def _detect_df_assignment(self, parsed):
        for n in ast.walk(parsed):
            if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = []
                if isinstance(n, ast.Assign):
                    targets.extend(n.targets)
                else:
                    targets.append(n.target)
                for t in targets:
                    if self._roots_at_df(t):
                        return True
        return False

    # ---------- execution (local only) ----------
    def _execute_local(self, code, parsed):
        stdout = io.StringIO()
        stderr = io.StringIO()

        sandbox_df = self.state.df.copy(deep=True)
        env = {
            "df": sandbox_df,
            "np": np,
            "pd": pd,
            "commit_df": False,
        }

        old_out, old_err = sys.stdout, sys.stderr
        committed_df = None
        success = False
        try:
            sys.stdout, sys.stderr = stdout, stderr

            env["_df_assignment"] = self._detect_df_assignment(parsed)
            last_value = None

            body = list(parsed.body)
            if body and isinstance(body[-1], ast.Expr):
                expr = ast.Expression(body.pop().value)
                exec(
                    compile(ast.Module(body=body, type_ignores=[]), "<exec>", "exec"),
                    env,
                    env,
                )
                last_value = eval(compile(expr, "<eval>", "eval"), env, env)
            else:
                exec(compile(parsed, "<exec>", "exec"), env, env)

            if (
                isinstance(last_value, tuple)
                and len(last_value) == 2
                and last_value[1]
                and isinstance(last_value[0], pd.DataFrame)
            ):
                committed_df = last_value[0]
                last_value = None
            elif env.get("commit_df") and isinstance(env.get("df"), pd.DataFrame):
                committed_df = env.get("df")
            elif env.get("_df_assignment", False) and isinstance(
                env.get("df"), pd.DataFrame
            ):
                committed_df = env.get("df")

            if last_value is not None:
                print(last_value)

            success = True
        except Exception as e:
            stderr.write(str(e))
        finally:
            sys.stdout, sys.stderr = old_out, old_err

        out_lines = stdout.getvalue().splitlines() + stderr.getvalue().splitlines()
        return out_lines, committed_df, success

    # ---------- public API ----------
    def execute(self, code):
        self._last_success = False
        try:
            parsed = ast.parse(code)
        except Exception as e:
            return [str(e)]

        lines, committed_df, success = self._execute_local(code, parsed)

        if committed_df is not None and success:
            self.state.df = committed_df
            if hasattr(self.state, "ensure_non_empty"):
                self.state.ensure_non_empty()

        self._last_success = success
        return lines
