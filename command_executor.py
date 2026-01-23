import ast
import builtins
import io
import os
import sys
import types
import tempfile
import subprocess

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

    def get_command_names(self):
        return sorted(self.config.get("COMMAND_REGISTER", {}).keys())

    def _bind_extensions(self, df, ext_flag=None):
        try:
            setattr(df, "vixl", VixlExtensions(df, self._extensions, ext_flag))
        except Exception:
            pass

    # ---------- external commands ----------
    def _write_input_files(self, tmpdir):
        in_csv = os.path.join(tmpdir, "in.csv")
        in_parquet = os.path.join(tmpdir, "in.parquet")
        try:
            self.state.df.to_csv(in_csv, index=False)
        except Exception:
            in_csv = None
        wrote_parquet = False
        try:
            self.state.df.to_parquet(in_parquet, index=False)
            wrote_parquet = True
        except Exception:
            in_parquet = None
        input_path = in_parquet if wrote_parquet else in_csv
        return input_path, in_csv, in_parquet

    def execute_registered_command(self, name, args):
        registry = self.config.get("COMMAND_REGISTER", {}) or {}
        spec = registry.get(name)
        if not spec:
            return [f"Unknown command: {name}"], None, False, None

        kind = spec.get("kind", "print")
        if kind not in {"print", "mutate"}:
            kind = "print"
        argv_tmpl = spec.get("argv") or []
        if not (
            isinstance(argv_tmpl, list) and all(isinstance(x, str) for x in argv_tmpl)
        ):
            return [f"Invalid argv for command: {name}"], None, False, kind
        timeout = spec.get("timeout_seconds") or 30

        with tempfile.TemporaryDirectory() as tmpdir:
            out_parquet = os.path.join(tmpdir, "out.parquet")
            out_text = os.path.join(tmpdir, "out.txt")
            input_path, in_csv, in_parquet = self._write_input_files(tmpdir)
            if not input_path:
                return ["Failed to materialize input df"], None, False, kind

            def _subst(tok):
                if tok == "{out_parquet}":
                    return out_parquet
                if tok == "{out_text}":
                    return out_text
                if tok == "{cwd}":
                    return tmpdir
                if tok.startswith("{arg") and tok.endswith("}"):
                    try:
                        idx = int(tok[4:-1])
                        return args[idx]
                    except Exception:
                        return ""
                if tok == "{args}":
                    return None  # marker to splice all args
                return tok

            argv = []
            for tok in argv_tmpl:
                if tok == "{args}":
                    argv.extend(args)
                    continue
                val = _subst(tok)
                if val is None:
                    argv.extend(args)
                else:
                    argv.append(val)

            # always append input_path as final arg
            argv.append(input_path)

            env = os.environ.copy()
            env.pop("PYTHONPATH", None)
            env.pop("PYTHONHOME", None)
            env.pop("LD_LIBRARY_PATH", None)
            env.pop("LD_PRELOAD", None)
            env.pop("DYLD_LIBRARY_PATH", None)
            env.pop("DYLD_FALLBACK_LIBRARY_PATH", None)

            env["VIXL_OUT_PARQUET"] = out_parquet
            env["VIXL_OUT_TEXT"] = out_text
            env["VIXL_CWD"] = tmpdir
            env["VIXL_IN"] = input_path
            if in_csv:
                env["VIXL_IN_CSV"] = in_csv
            if in_parquet:
                env["VIXL_IN_PARQUET"] = in_parquet

            proc = subprocess.run(
                argv,
                text=True,
                capture_output=True,
                timeout=timeout,
                cwd=tmpdir,
                env=env,
            )

            lines = []
            committed_df = None

            if proc.returncode != 0:
                if proc.stdout:
                    lines.extend(proc.stdout.splitlines())
                if proc.stderr:
                    lines.extend(proc.stderr.splitlines())
                return lines or ["Command failed"], None, False, kind

            if kind == "mutate":
                if os.path.exists(out_parquet):
                    try:
                        committed_df = pd.read_parquet(out_parquet)
                    except Exception as e:
                        lines.append(f"Failed to load parquet: {e}")
                        return lines, None, False, kind
                else:
                    return ["Mutating command produced no parquet"], None, False, kind

            # collect text output for both kinds
            if os.path.exists(out_text):
                try:
                    with open(out_text, "r", encoding="utf-8") as f:
                        lines.extend(f.read().splitlines())
                except Exception:
                    pass
            if proc.stdout and not lines:
                lines.extend(proc.stdout.splitlines())
            if proc.stderr and not lines:
                lines.extend(proc.stderr.splitlines())

            if kind == "mutate" and committed_df is not None:
                lines = []  # suppress successful mutate output

            return lines, committed_df, True, kind

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
