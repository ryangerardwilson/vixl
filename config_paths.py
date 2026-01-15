import os

HOME = os.path.expanduser("~")
XDG_CONFIG_HOME = os.environ.get("XDG_CONFIG_HOME")
CONFIG_HOME = XDG_CONFIG_HOME if XDG_CONFIG_HOME else os.path.join(HOME, ".config")
CONFIG_DIR = os.path.join(CONFIG_HOME, "vixl")
HISTORY_PATH = os.path.join(CONFIG_DIR, "history.log")
EXTENSIONS_DIR = os.path.join(CONFIG_DIR, "extensions")
EXTENSIONS_PY = os.path.join(CONFIG_DIR, "extensions.py")
CONFIG_JSON = os.path.join(CONFIG_DIR, "config.json")

# default settings
EXPRESSION_REGISTER_DEFAULT = []
CLIPBOARD_INTERFACE_COMMAND_DEFAULT = None
PYTHON_PATH_DEFAULT = None


def ensure_config_dirs():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.makedirs(EXTENSIONS_DIR, exist_ok=True)
    if not os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "w", encoding="utf-8") as f:
                f.write("")
        except Exception:
            pass


def load_config():
    cfg = {
        "EXPRESSION_REGISTER": list(EXPRESSION_REGISTER_DEFAULT),
        "CLIPBOARD_INTERFACE_COMMAND": CLIPBOARD_INTERFACE_COMMAND_DEFAULT,
        "PYTHON_PATH": PYTHON_PATH_DEFAULT,
    }

    if os.path.exists(CONFIG_JSON):
        try:
            import json

            with open(CONFIG_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                cmd_mode = data.get("cmd_mode")
                reg = (
                    cmd_mode.get("expression_register")
                    if isinstance(cmd_mode, dict)
                    else None
                )
                if isinstance(reg, list):
                    cfg["EXPRESSION_REGISTER"] = [
                        str(item) for item in reg if isinstance(item, str)
                    ]
                clip_cmd = data.get("clipboard_interface_command")
                if isinstance(clip_cmd, list) and all(
                    isinstance(item, str) for item in clip_cmd
                ):
                    cfg["CLIPBOARD_INTERFACE_COMMAND"] = clip_cmd

                py_path = data.get("python_path")
                if isinstance(py_path, str) and py_path.strip():
                    cfg["PYTHON_PATH"] = py_path
        except Exception:
            pass

    return cfg
