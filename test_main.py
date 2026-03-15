import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


APP_DIR = Path(__file__).resolve().parent
MAIN_PATH = APP_DIR / "main.py"
VERSION_PATH = APP_DIR / "_version.py"
CONTRACT_SRC = APP_DIR.parent / "rgw_cli_contract" / "src"

sys.path.insert(0, str(APP_DIR))
if CONTRACT_SRC.exists():
    sys.path.insert(0, str(CONTRACT_SRC))


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
    def test_app_spec_uses_single_version_source(self):
        module = load_main_module()

        self.assertEqual(module.APP_SPEC.version, load_version())
        self.assertEqual(module.APP_SPEC.app_name, "vixl")
        self.assertEqual(module.APP_SPEC.no_args_mode, "dispatch")

    def test_config_path_factory_returns_config_json_path(self):
        module = load_main_module()

        self.assertEqual(
            module.APP_SPEC.config_path_factory(),
            Path(module.config_paths.CONFIG_JSON),
        )

    def test_main_delegates_to_contract_runtime(self):
        module = load_main_module()

        with mock.patch.object(module, "run_app", return_value=0) as run_app:
            rc = module.main(["data.csv"])

        self.assertEqual(rc, 0)
        self.assertEqual(run_app.call_args.args[0], module.APP_SPEC)
        self.assertEqual(run_app.call_args.args[1], ["data.csv"])
        self.assertIs(run_app.call_args.args[2], module._dispatch)


if __name__ == "__main__":
    unittest.main()
