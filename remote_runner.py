#!/usr/bin/env python3
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

    setattr(env["df"], "vixl", VixlExtensions(env["df"], extensions, ext_flag=ext_called_flag))

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
