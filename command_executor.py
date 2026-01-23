import ast
import builtins
import io
import os
import sys
import types

import numpy as np
import pandas as pd

from config_paths import EXTENSIONS_DIR, EXTENSIONS_PY, ensure_config_dirs, load_config

_ALLOWED_GLOBALS = {"df", "pd", "np", "commit_df"}
_ESCAPE_HATCH_NAMES = {
    "__import__",
    "eval",
    "exec",
    "compile",
    "open",
    "input",
    "globals",
    "locals",
    "vars",
    "importlib",
}
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


class VixlExtensions:
    def __init__(self, df, extensions, ext_flag=None):
        self._df = df
        self._extensions = extensions
        self._ext_flag = ext_flag
        self._cache = {}

    def __getattr__(self, name):
        if name not in self._extensions:
            raise AttributeError(f"No extension named '{name}'")
        if name in self._cache:
            return self._cache[name]

        fn = self._extensions[name]

        def _wrapped(*args, **kwargs):
            if self._ext_flag is not None:
                self._ext_flag[0] = True
            return fn(self._df, *args, **kwargs)

        self._cache[name] = _wrapped
        return _wrapped

    def __dir__(self):
        return sorted(self._extensions.keys())


class CommandExecutor:
    def __init__(self, app_state):
        self.state = app_state
        self.startup_warnings = []
        ensure_config_dirs()
        self.config = load_config()

        ignored_cmds = self.config.get("IGNORED_COMMAND_ENTRIES") or []
        if ignored_cmds:
            names = ", ".join(ignored_cmds)
            plural = "ies" if len(ignored_cmds) != 1 else "y"
            self.startup_warnings.append(
                f"Ignored command register entr{plural}: {names}"
            )

        self._warn_deprecated_extensions_dir()
        self._extensions = self._load_extensions()
        self._extension_names = sorted(self._extensions.keys())

    # ---------- config / warnings ----------
    def _warn_deprecated_extensions_dir(self):
        if not os.path.isdir(EXTENSIONS_DIR):
            return
        for fname in os.listdir(EXTENSIONS_DIR):
            if fname.endswith(".py"):
                self.startup_warnings.append(
                    "extensions directory is deprecated; move to ~/.config/vixl/extensions.py"
                )
                break

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

    # ---------- extensions ----------
    def _validate_extensions_ast(self, parsed):
        for n in ast.walk(parsed):
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                raise ValueError("imports are not allowed in extensions.py")
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                if n.id in _ESCAPE_HATCH_NAMES:
                    raise ValueError(f"disallowed name in extensions.py: {n.id}")
        return True

    def _load_extensions(self):
        funcs = {}
        if not os.path.exists(EXTENSIONS_PY):
            return funcs
        try:
            with open(EXTENSIONS_PY, "r", encoding="utf-8") as f:
                src = f.read()
            parsed = ast.parse(src, filename=EXTENSIONS_PY)
            self._validate_extensions_ast(parsed)

            g = {"__builtins__": _SAFE_BUILTINS, "pd": pd, "np": np}
            exec(compile(parsed, EXTENSIONS_PY, "exec"), g, g)
            for name, val in list(g.items()):
                if isinstance(val, types.FunctionType) and not name.startswith("_"):
                    funcs[name] = val
        except Exception as e:
            self.startup_warnings.append(f"failed to load extensions.py: {e}")
        return funcs

    def get_extension_names(self):
        return list(self._extension_names)

    def _bind_extensions(self, df, ext_flag=None):
        try:
            setattr(df, "vixl", VixlExtensions(df, self._extensions, ext_flag))
        except Exception:
            pass

    # ---------- execution (local only) ----------
    def _execute_local(self, code, parsed):
        stdout = io.StringIO()
        stderr = io.StringIO()

        # ensure current df has extensions bound
        self._bind_extensions(self.state.df)

        sandbox_df = self.state.df.copy(deep=True)
        ext_called_flag = [False]
        env = {
            "df": sandbox_df,
            "np": np,
            "pd": pd,
            "commit_df": False,
            "_ext_called": ext_called_flag,
        }
        # bind extensions to sandbox df with flagging
        self._bind_extensions(env["df"], ext_flag=ext_called_flag)

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
            self._bind_extensions(self.state.df)
            if hasattr(self.state, "ensure_non_empty"):
                self.state.ensure_non_empty()

        self._last_success = success
        return lines
