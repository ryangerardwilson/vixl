import contextlib
import importlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path


@contextlib.contextmanager
def _completion_env(tmp_path: str, env_updates: dict | None = None, remove: list[str] | None = None):
    env_updates = env_updates or {}
    remove = remove or []
    tracked_keys = {"HOME", *env_updates.keys(), *remove}
    previous = {key: os.environ.get(key) for key in tracked_keys}
    try:
        os.environ["HOME"] = tmp_path
        for key in remove:
            os.environ.pop(key, None)
        os.environ.update(env_updates)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _load_handler_module():
    if "completions_handler" in sys.modules:
        del sys.modules["completions_handler"]
    module = importlib.import_module("completions_handler")
    return importlib.reload(module)


def _write_marker_block(rc_path: Path, handler_mod) -> None:
    rc_path.write_text(
        "\n".join(
            [
                handler_mod.CompletionHandler.BASHRC_MARKER_BEGIN,
                'if [ -f "$HOME/.config/vixl/completions/vixl.bash" ]; then',
                '    source "$HOME/.config/vixl/completions/vixl.bash"',
                "fi",
                handler_mod.CompletionHandler.BASHRC_MARKER_END,
                "",
            ]
        )
    )


class CompletionHandlerGuardTests(unittest.TestCase):
    def test_warns_but_does_not_block_when_inactive(self):
        with tempfile.TemporaryDirectory() as tmpdir, _completion_env(
            tmpdir, remove=["VIXL_BASH_COMPLETION_ACTIVE", "VIXL_SKIP_COMPLETION_CHECK"]
        ):
            handler_mod = _load_handler_module()
            handler = handler_mod.CompletionHandler()

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                handler.ensure_ready()

            output = buf.getvalue()
            self.assertIn("continuing without completion", output)
            self.assertIn(handler_mod.CompletionHandler.SKIP_CHECK_ENV, output)
            self.assertTrue(handler_mod.CompletionHandler.BASH_COMPLETION_FILE.exists())

    def test_skip_env_bypasses_warning(self):
        with tempfile.TemporaryDirectory() as tmpdir, _completion_env(
            tmpdir,
            env_updates={"VIXL_SKIP_COMPLETION_CHECK": "1"},
            remove=["VIXL_BASH_COMPLETION_ACTIVE"],
        ):
            handler_mod = _load_handler_module()
            handler = handler_mod.CompletionHandler()

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                handler.ensure_ready()

            self.assertEqual(buf.getvalue(), "")
            self.assertTrue(handler_mod.CompletionHandler.BASH_COMPLETION_FILE.exists())

    def test_env_marker_alone_suppresses_warning(self):
        with tempfile.TemporaryDirectory() as tmpdir, _completion_env(
            tmpdir, env_updates={"VIXL_BASH_COMPLETION_ACTIVE": "1"}, remove=["VIXL_SKIP_COMPLETION_CHECK"]
        ):
            handler_mod = _load_handler_module()
            handler = handler_mod.CompletionHandler()

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                handler.ensure_ready()

            self.assertEqual(buf.getvalue(), "")

    def test_rc_marker_alone_suppresses_warning(self):
        with tempfile.TemporaryDirectory() as tmpdir, _completion_env(
            tmpdir, remove=["VIXL_BASH_COMPLETION_ACTIVE", "VIXL_SKIP_COMPLETION_CHECK"]
        ):
            handler_mod = _load_handler_module()
            handler = handler_mod.CompletionHandler()

            rc_path = Path(tmpdir) / ".bashrc"
            rc_path.touch()
            _write_marker_block(rc_path, handler_mod)

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                handler.ensure_ready()

            self.assertEqual(buf.getvalue(), "")

    def test_rc_marker_in_bash_profile_with_bashrc_present_is_detected(self):
        with tempfile.TemporaryDirectory() as tmpdir, _completion_env(
            tmpdir, remove=["VIXL_BASH_COMPLETION_ACTIVE", "VIXL_SKIP_COMPLETION_CHECK"]
        ):
            handler_mod = _load_handler_module()
            handler = handler_mod.CompletionHandler()

            bashrc = Path(tmpdir) / ".bashrc"
            bashrc.write_text("# empty rc\n")
            bash_profile = Path(tmpdir) / ".bash_profile"
            _write_marker_block(bash_profile, handler_mod)

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                handler.ensure_ready()

            self.assertEqual(buf.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
