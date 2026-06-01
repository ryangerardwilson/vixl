import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest import mock


APP_DIR = Path(__file__).resolve().parent
MAIN_PATH = APP_DIR / "main.py"
VERSION_PATH = APP_DIR / "_version.py"

sys.path.insert(0, str(APP_DIR))


def load_main_module():
    spec = importlib.util.spec_from_file_location("vixl_main_test", MAIN_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_version():
    namespace = {}
    exec(VERSION_PATH.read_text(encoding="utf-8"), namespace)
    return namespace["__version__"]


class MainContractTests(unittest.TestCase):
    def test_version_uses_single_version_source(self):
        module = load_main_module()

        with mock.patch("builtins.print") as print_mock:
            rc = module.main(["-v"])

        self.assertEqual(rc, 0)
        print_mock.assert_called_once_with(load_version())

    def test_no_args_prints_help(self):
        module = load_main_module()

        with mock.patch.object(module, "_print_help") as print_help:
            rc = module.main([])

        self.assertEqual(rc, 0)
        print_help.assert_called_once_with()

    def test_main_dispatches_open_command(self):
        module = load_main_module()

        with mock.patch.object(module, "_dispatch", return_value=0) as dispatch:
            rc = module.main(["open", "data.csv"])

        self.assertEqual(rc, 0)
        dispatch.assert_called_once_with(["open", "data.csv"])

    def test_config_opens_config_path(self):
        module = load_main_module()

        with mock.patch.object(module.config_paths, "ensure_config_dirs") as ensure_dirs:
            with mock.patch.object(module.config_paths, "CONFIG_JSON", "/tmp/vixl-config.json"):
                with mock.patch.object(Path, "exists", return_value=True):
                    with mock.patch("subprocess.run") as run:
                        run.return_value.returncode = 0
                        with mock.patch.dict(os.environ, {"EDITOR": "/usr/bin/true"}, clear=True):
                            rc = module.main(["config"])

        self.assertEqual(rc, 0)
        ensure_dirs.assert_called_once_with()
        run.assert_called_once_with(
            ["/usr/bin/true", "/tmp/vixl-config.json"],
            check=False,
        )


if __name__ == "__main__":
    unittest.main()
