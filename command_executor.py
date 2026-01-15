import ast
import builtins
import importlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import types
from typing import Optional, Tuple

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
_BUILTINS = set(dir(builtins))

_REMOTE_RUNNER_CODE = r"""
import argparse
import ast
import importlib.util
import io
import json
import os
import sys
import types

import pandas as pd
import numpy as np


def _roots_at_df(node):
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


def _detect_df_assignment(parsed):
    for n in ast.walk(parsed):
        if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = []
            if isinstance(n, ast.Assign):
                targets.extend(n.targets)
            else:
                targets.append(n.target)
            for t in targets:
                if _roots_at_df(t):
                    return True
    return False


def _load_extensions_from_file(path):
    funcs = {}
    if not path or not os.path.exists(path):
        return funcs
    spec = importlib.util.spec_from_file_location("vixl_user_extensions", path)
    if not spec or not spec.loader:
        return funcs
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        return funcs
    for name in dir(mod):
        if name.startswith("_"):
            continue
        attr = getattr(mod, name)
        if isinstance(attr, types.FunctionType):
            funcs[name] = attr
    return funcs


def _serialize_df(df, path):
    try:
        import pyarrow as pa
        import pyarrow.ipc as ipc

        table = pa.Table.from_pandas(df, preserve_index=True)
        with ipc.new_file(path, table.schema) as writer:
            writer.write_table(table)
        return "arrow"
    except Exception:
        import pickle

        with open(path, "wb") as f:
            pickle.dump(df, f, protocol=pickle.HIGHEST_PROTOCOL)
        return "pickle"


def _deserialize_df(path, fmt):
    if fmt == "arrow":
        import pyarrow.ipc as ipc

        with ipc.open_file(path) as reader:
            return reader.read_pandas()
    import pickle

    with open(path, "rb") as f:
        return pickle.load(f)


class _VixlExtensions:
    def __init__(self, df, extensions, flag=None):
        self._df = df
        self._extensions = extensions
        self._flag = flag
        self._cache = {}

    def __getattr__(self, name):
        if name not in self._extensions:
            raise AttributeError(f"No extension named '{name}'")
        if name in self._cache:
            return self._cache[name]

        fn = self._extensions[name]

        def _wrapped(*args, **kwargs):
            if self._flag is not None:
                self._flag[0] = True
            return fn(self._df, *args, **kwargs)

        self._cache[name] = _wrapped
        return _wrapped


def _run_code(code, df, extensions):
    stdout = io.StringIO()
    stderr = io.StringIO()

    sandbox_df = df.copy(deep=True)
    ext_called_flag = [False]
    env = {
        "df": sandbox_df,
        "np": np,
        "pd": pd,
        "commit_df": False,
        "_ext_called": ext_called_flag,
    }
    setattr(env["df"], "vixl", _VixlExtensions(env["df"], extensions, flag=ext_called_flag))

    parsed = ast.parse(code)
    env["_df_assignment"] = _detect_df_assignment(parsed)
    last_value = None
    committed_df = None
    ok = False

    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = stdout, stderr

        body = list(parsed.body)
        if body and isinstance(body[-1], ast.Expr):
            expr = ast.Expression(body.pop().value)
            exec(compile(ast.Module(body=body, type_ignores=[]), "<exec>", "exec"), env, env)
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
        elif env.get("_df_assignment", False) and isinstance(env.get("df"), pd.DataFrame):
            committed_df = env.get("df")

        if last_value is not None:
            print(last_value)

        ok = True
    except Exception as e:
        stderr.write(str(e))
    finally:
        sys.stdout, sys.stderr = old_out, old_err

    return {
        "ok": ok,
        "stdout": stdout.getvalue().splitlines(),
        "stderr": stderr.getvalue().splitlines(),
        "committed_df": committed_df,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--response", required=True)
    parser.add_argument("--in-df", required=True)
    parser.add_argument("--out-df", required=True)
    args = parser.parse_args(argv)

    with open(args.request, "r", encoding="utf-8") as f:
        req = json.load(f)

    code = req.get("code", "")
    ext_path = req.get("extensions_path")
    df_format = req.get("df_format")

    df = _deserialize_df(args.in_df, df_format)
    extensions = _load_extensions_from_file(ext_path)

    result = _run_code(code, df, extensions)

    resp = {
        "ok": result.get("ok", False),
        "stdout": result.get("stdout", []),
        "stderr": result.get("stderr", []),
        "committed": False,
        "df_format": None,
    }

    if result.get("committed_df") is not None:
        out_fmt = _serialize_df(result["committed_df"], args.out_df)
        resp["committed"] = True
        resp["df_format"] = out_fmt

    with open(args.response, "w", encoding="utf-8") as f:
        json.dump(resp, f)

    return 0 if resp.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
"""


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

        self._python_path = self._validate_python_path()
        self._warn_deprecated_extensions_dir()
        self._extension_names = self._load_extension_names()
        # We no longer import user extensions locally for execution; any df.vixl
        # usage routes to remote. Keep empty dict to satisfy the binder.
        self._extensions = {}

    # ---------- config / warnings ----------
    def _validate_python_path(self) -> Optional[str]:
        python_path = self.config.get("PYTHON_PATH")
        if not isinstance(python_path, str) or not python_path.strip():
            return None

        path = os.path.expanduser(os.path.expandvars(python_path.strip()))
        if not (os.path.isfile(path) and os.access(path, os.X_OK)):
            self.startup_warnings.append(f"python_path is not executable: {path}")
            return None

        return path

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

    def _uses_df_vixl(self, parsed) -> bool:
        for n in ast.walk(parsed):
            if isinstance(n, ast.Attribute) and getattr(n, "attr", None) == "vixl":
                base = n.value
                while isinstance(base, ast.Attribute):
                    base = base.value
                if isinstance(base, ast.Name) and base.id == "df":
                    return True
        return False

    def _collect_defined_loaded(self, parsed):
        defined = set()
        loaded = set()

        class Visitor(ast.NodeVisitor):
            def visit_Name(self, node):
                if isinstance(node.ctx, ast.Store):
                    defined.add(node.id)
                elif isinstance(node.ctx, ast.Load):
                    loaded.add(node.id)
                self.generic_visit(node)

            def visit_FunctionDef(self, node):
                defined.add(node.name)
                for arg in node.args.args + node.args.kwonlyargs:
                    defined.add(arg.arg)
                if node.args.vararg:
                    defined.add(node.args.vararg.arg)
                if node.args.kwarg:
                    defined.add(node.args.kwarg.arg)
                self.generic_visit(node)

            def visit_AsyncFunctionDef(self, node):
                Visitor.visit_FunctionDef(self, node)  # type: ignore[arg-type]

            def visit_ClassDef(self, node):
                defined.add(node.name)
                self.generic_visit(node)

        Visitor().visit(parsed)
        return defined, loaded

    def _should_execute_remote(self, code: str, parsed) -> Tuple[bool, str]:
        reasons = []

        # imports => remote
        for n in ast.walk(parsed):
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                reasons.append("import present")
                break

        # df.vixl usage => remote
        if self._uses_df_vixl(parsed):
            reasons.append("df.vixl usage")

        defined, loaded = self._collect_defined_loaded(parsed)
        free = loaded - defined - _ALLOWED_GLOBALS - _BUILTINS
        if free:
            reasons.append(f"unknown names: {', '.join(sorted(free))}")

        escape_used = loaded.intersection(_ESCAPE_HATCH_NAMES)
        if escape_used:
            reasons.append(f"escape hatch: {', '.join(sorted(escape_used))}")

        if reasons:
            return True, "; ".join(reasons)
        return False, "local: only builtins/df/np/pd"

    # ---------- extensions ----------
    def _load_extension_names(self):
        names = []
        if not os.path.exists(EXTENSIONS_PY):
            return names
        try:
            with open(EXTENSIONS_PY, "r", encoding="utf-8") as f:
                src = f.read()
            parsed = ast.parse(src, filename=EXTENSIONS_PY)
            for node in parsed.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not node.name.startswith("_"):
                        names.append(node.name)
        except Exception:
            self.startup_warnings.append(
                f"failed to inspect extensions.py; completions may be missing"
            )
        return sorted(set(names))

    def get_extension_names(self):
        return list(self._extension_names)

    def _bind_extensions(self, df, ext_flag=None):
        try:
            setattr(df, "vixl", VixlExtensions(df, self._extensions, ext_flag))
        except Exception:
            pass

    # ---------- serialization helpers ----------
    def _serialize_df(self, df, path):
        try:
            import pyarrow as pa
            import pyarrow.ipc as ipc

            table = pa.Table.from_pandas(df, preserve_index=True)
            with ipc.new_file(path, table.schema) as writer:
                writer.write_table(table)
            return "arrow"
        except Exception:
            import pickle

            with open(path, "wb") as f:
                pickle.dump(df, f, protocol=pickle.HIGHEST_PROTOCOL)
            return "pickle"

    def _deserialize_df(self, path, fmt):
        if fmt == "arrow":
            import pyarrow.ipc as ipc

            with ipc.open_file(path) as reader:
                return reader.read_pandas()
        import pickle

        with open(path, "rb") as f:
            return pickle.load(f)

    # ---------- execution backends ----------
    def _execute_local(self, code, parsed):
        stdout = io.StringIO()
        stderr = io.StringIO()

        # ensure current df has extensions bound (empty in local mode)
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
                exec(compile(ast.Module(body=body, type_ignores=[]), "<exec>", "exec"), env, env)
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
            elif env.get("_df_assignment", False) and isinstance(env.get("df"), pd.DataFrame):
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

    def _execute_remote(self, code, parsed, reason):
        if not self._python_path:
            return [f"Remote execution required ({reason}) but python_path is not configured"], None, False

        with tempfile.TemporaryDirectory() as tmpdir:
            in_df_path = os.path.join(tmpdir, "in.df")
            out_df_path = os.path.join(tmpdir, "out.df")
            req_path = os.path.join(tmpdir, "req.json")
            resp_path = os.path.join(tmpdir, "resp.json")

            df_format = self._serialize_df(self.state.df, in_df_path)
            request = {
                "code": code,
                "extensions_path": EXTENSIONS_PY,
                "df_format": df_format,
            }
            with open(req_path, "w", encoding="utf-8") as f:
                json.dump(request, f)

            clean_env = os.environ.copy()
            clean_env.pop("PYTHONPATH", None)
            clean_env.pop("PYTHONHOME", None)

            proc = subprocess.run(
                [
                    self._python_path,
                    "-c",
                    _REMOTE_RUNNER_CODE,
                    "--request",
                    req_path,
                    "--response",
                    resp_path,
                    "--in-df",
                    in_df_path,
                    "--out-df",
                    out_df_path,
                ],
                text=True,
                capture_output=True,
                timeout=30,
                cwd=tmpdir,
                env=clean_env,
            )

            has_response = os.path.exists(resp_path)
            resp = None
            if has_response:
                try:
                    with open(resp_path, "r", encoding="utf-8") as f:
                        resp = json.load(f)
                except Exception as e:
                    return [f"Failed to read remote response: {e}"], None, False

            if proc.returncode != 0:
                lines = []
                if resp is not None:
                    lines.extend(resp.get("stdout") or [])
                    lines.extend(resp.get("stderr") or [])
                if proc.stdout:
                    lines.extend(proc.stdout.splitlines())
                if proc.stderr:
                    lines.extend(proc.stderr.splitlines())
                lines.insert(0, f"Remote execution failed ({reason})")
                return lines, None, False

            if resp is None:
                return ["Remote runner produced no response"], None, False

            lines = (resp.get("stdout") or []) + (resp.get("stderr") or [])
            success = bool(resp.get("ok"))
            committed_df = None
            if resp.get("committed") and os.path.exists(out_df_path):
                try:
                    committed_df = self._deserialize_df(out_df_path, resp.get("df_format"))
                except Exception as e:
                    lines.append(f"Failed to read remote dataframe: {e}")
                    success = False

            return lines, committed_df, success

    # ---------- public API ----------
    def execute(self, code):
        self._last_success = False
        try:
            parsed = ast.parse(code)
        except Exception as e:
            return [str(e)]

        use_remote, reason = self._should_execute_remote(code, parsed)

        if use_remote:
            lines, committed_df, success = self._execute_remote(code, parsed, reason)
        else:
            lines, committed_df, success = self._execute_local(code, parsed)

        if committed_df is not None and success:
            self.state.df = committed_df
            self._bind_extensions(self.state.df)
            if hasattr(self.state, "ensure_non_empty"):
                self.state.ensure_non_empty()

        self._last_success = success
        return lines
