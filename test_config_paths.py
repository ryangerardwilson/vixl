import json
import tempfile
from pathlib import Path

import config_paths


def test_load_config_defaults_without_json():
    with tempfile.TemporaryDirectory() as tmp:
        cfg_dir = Path(tmp) / "vixl"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        # point module paths to temp
        orig_dir = config_paths.CONFIG_DIR
        orig_json = config_paths.CONFIG_JSON
        try:
            config_paths.CONFIG_DIR = str(cfg_dir)
            config_paths.CONFIG_JSON = str(cfg_dir / "config.json")
            cfg = config_paths.load_config()
            cfg = config_paths.load_config()
            assert "AUTO_COMMIT" not in cfg
            assert cfg["TAB_FUZZY_EXPANSIONS_REGISTER"] == []
            assert cfg["PYTHON_PATH"] is None

        finally:
            config_paths.CONFIG_DIR = orig_dir
            config_paths.CONFIG_JSON = orig_json


def test_load_config_reads_json_overrides():
    with tempfile.TemporaryDirectory() as tmp:
        cfg_dir = Path(tmp) / "vixl"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        cfg_path = cfg_dir / "config.json"
        cfg_path.write_text(
            json.dumps(
                {
                    "python_path": "/tmp/venv/bin/python",
                    "cmd_mode": {
                        "tab_fuzzy_expansions_register": [
                            "df.vixl.foo()",
                            "df.bar()",
                        ]
                    },
                }
            )
        )

        orig_dir = config_paths.CONFIG_DIR
        orig_json = config_paths.CONFIG_JSON
        try:
            config_paths.CONFIG_DIR = str(cfg_dir)
            config_paths.CONFIG_JSON = str(cfg_path)
            cfg = config_paths.load_config()
            assert "AUTO_COMMIT" not in cfg
            assert cfg["TAB_FUZZY_EXPANSIONS_REGISTER"] == [
                "df.vixl.foo()",
                "df.bar()",
            ]
            assert cfg["PYTHON_PATH"] == "/tmp/venv/bin/python"
        finally:
            config_paths.CONFIG_DIR = orig_dir
            config_paths.CONFIG_JSON = orig_json


def test_load_config_ignores_non_string_python_path():
    with tempfile.TemporaryDirectory() as tmp:
        cfg_dir = Path(tmp) / "vixl"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        cfg_path = cfg_dir / "config.json"
        cfg_path.write_text(json.dumps({"python_path": 123}))

        orig_dir = config_paths.CONFIG_DIR
        orig_json = config_paths.CONFIG_JSON
        try:
            config_paths.CONFIG_DIR = str(cfg_dir)
            config_paths.CONFIG_JSON = str(cfg_path)
            cfg = config_paths.load_config()
            assert cfg["PYTHON_PATH"] is None
        finally:
            config_paths.CONFIG_DIR = orig_dir
            config_paths.CONFIG_JSON = orig_json
