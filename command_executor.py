import io
import sys
import os
import importlib.util
import types
import numpy as np
import pandas as pd

from config_paths import EXTENSIONS_DIR, ensure_config_dirs, load_config


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
        ensure_config_dirs()
        self.config = load_config()
        self._extensions = self._load_extensions()

    # ---------- extensions ----------
    def _load_extensions(self):
        funcs = {}
        if not os.path.exists(EXTENSIONS_DIR):
            return funcs

        for fname in sorted(os.listdir(EXTENSIONS_DIR)):
            if not fname.endswith(".py"):
                continue
            path = os.path.join(EXTENSIONS_DIR, fname)
            spec = importlib.util.spec_from_file_location(f"vixl_ext_{fname}", path)
            if not spec or not spec.loader:
                continue
            mod = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(mod)
            except Exception:
                # swallow extension load errors; user can inspect their files
                continue
            for name in dir(mod):
                if name.startswith("_"):
                    continue
                attr = getattr(mod, name)
                if isinstance(attr, types.FunctionType):
                    funcs[name] = attr
        return funcs

    def get_extension_names(self):
        return sorted(self._extensions.keys())

    def _bind_extensions(self, df, ext_flag=None):
        try:
            setattr(df, "vixl", VixlExtensions(df, self._extensions, ext_flag))
        except Exception:
            pass

    # ---------- execution ----------
    def execute(self, code):
        self._last_success = False
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

        auto_commit = bool(self.config.get("AUTO_COMMIT", False))

        import ast

        old_out, old_err = sys.stdout, sys.stderr
        try:
            sys.stdout, sys.stderr = stdout, stderr

            parsed = ast.parse(code)
            last_value = None

            if parsed.body and isinstance(parsed.body[-1], ast.Expr):
                expr = ast.Expression(parsed.body.pop().value)
                exec(compile(parsed, "<exec>", "exec"), env, env)
                last_value = eval(compile(expr, "<eval>", "eval"), env, env)
            else:
                exec(code, env, env)

            committed_df = None

            # handle mutation-signaling tuple: (df_like, truthy_flag)
            if (
                isinstance(last_value, tuple)
                and len(last_value) == 2
                and last_value[1]
                and isinstance(last_value[0], pd.DataFrame)
            ):
                committed_df = last_value[0]
                last_value = None  # suppress printing of the mutation tuple
            elif env.get("commit_df") and isinstance(env.get("df"), pd.DataFrame):
                committed_df = env.get("df")
            elif not env.get("_ext_called", [False])[0] and isinstance(
                env.get("df"), pd.DataFrame
            ):
                # natural command (no extension calls) commits by default
                committed_df = env.get("df")
            elif auto_commit and isinstance(env.get("df"), pd.DataFrame):
                committed_df = env.get("df")

            if committed_df is not None:
                self.state.df = committed_df
                # rebind extensions on updated df
                self._bind_extensions(self.state.df)
                # ensure grid-safe invariant
                if hasattr(self.state, "ensure_non_empty"):
                    self.state.ensure_non_empty()
            else:
                # no explicit commit: leave df unchanged and no rebind needed
                pass

            if last_value is not None:
                print(last_value)

            self._last_success = True
        except Exception as e:
            stderr.write(str(e))
        finally:
            sys.stdout, sys.stderr = old_out, old_err
        out_lines = stdout.getvalue().splitlines() + stderr.getvalue().splitlines()
        return out_lines
