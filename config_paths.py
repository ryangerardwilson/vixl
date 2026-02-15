import os

HOME = os.path.expanduser("~")
XDG_CONFIG_HOME = os.environ.get("XDG_CONFIG_HOME")
CONFIG_HOME = XDG_CONFIG_HOME if XDG_CONFIG_HOME else os.path.join(HOME, ".config")
CONFIG_DIR = os.path.join(CONFIG_HOME, "vixl")
HISTORY_PATH = os.path.join(CONFIG_DIR, "history.log")
CONFIG_JSON = os.path.join(CONFIG_DIR, "config.json")

# default settings
CLIPBOARD_INTERFACE_COMMAND_DEFAULT = None


def ensure_config_dirs():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "w", encoding="utf-8") as f:
                f.write("")
        except Exception:
            pass


def load_config():
    cfg = {
        "CLIPBOARD_INTERFACE_COMMAND": CLIPBOARD_INTERFACE_COMMAND_DEFAULT,
        "IGNORED_COMMAND_ENTRIES": [],
    }

    if os.path.exists(CONFIG_JSON):
        try:
            import json

            with open(CONFIG_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                clip_cmd = data.get("clipboard_interface_command")
                if isinstance(clip_cmd, list) and all(
                    isinstance(item, str) for item in clip_cmd
                ):
                    cfg["CLIPBOARD_INTERFACE_COMMAND"] = clip_cmd

        except Exception:
            pass

    return cfg
