import json
import os
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
            assert cfg["AUTO_COMMIT"] is False
            assert cfg["TAB_FUZZY_EXPANSIONS_REGISTER"] == []
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
                    "AUTO_COMMIT": True,
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
            assert cfg["AUTO_COMMIT"] is True
            assert cfg["TAB_FUZZY_EXPANSIONS_REGISTER"] == [
                "df.vixl.foo()",
                "df.bar()",
            ]
        finally:
            config_paths.CONFIG_DIR = orig_dir
            config_paths.CONFIG_JSON = orig_json
