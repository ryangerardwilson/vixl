import pandas as pd
import pytest

import command_executor as ce


class DummyState:
    def __init__(self):
        self.df = pd.DataFrame({"a": [1], "b": [2]})


@pytest.fixture(autouse=True)
def patch_config(monkeypatch):
    monkeypatch.setattr(ce, "load_config", lambda: {})


def _make_executor(monkeypatch):
    # avoid reading user config and extensions
    exec_obj = ce.CommandExecutor(DummyState())
    return exec_obj


def test_local_route_simple_assignment(monkeypatch):
    exec_obj = _make_executor(monkeypatch)
    parsed = ce.ast.parse("df['c'] = df['a'] + df['b']")
    use_remote, reason = exec_obj._should_execute_remote("df['c'] = df['a'] + df['b']", parsed)
    assert use_remote is False
    assert "local" in reason


def test_remote_route_on_import(monkeypatch):
    exec_obj = _make_executor(monkeypatch)
    code = "import math\nmath.sqrt(4)"
    parsed = ce.ast.parse(code)
    use_remote, reason = exec_obj._should_execute_remote(code, parsed)
    assert use_remote is True
    assert "import" in reason


def test_remote_route_on_df_vixl(monkeypatch):
    exec_obj = _make_executor(monkeypatch)
    code = "df.vixl.foo()"
    parsed = ce.ast.parse(code)
    use_remote, reason = exec_obj._should_execute_remote(code, parsed)
    assert use_remote is True
    assert "df.vixl" in reason
