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
COMMAND_REGISTER_DEFAULT = {}
CLIPBOARD_INTERFACE_COMMAND_DEFAULT = None


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
        "COMMAND_REGISTER": dict(COMMAND_REGISTER_DEFAULT),
        "CLIPBOARD_INTERFACE_COMMAND": CLIPBOARD_INTERFACE_COMMAND_DEFAULT,
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

                cmd_reg = None
                cmd_mode = data.get("cmd_mode") if isinstance(data, dict) else None
                if isinstance(cmd_mode, dict):
                    cmd_reg = cmd_mode.get("command_register")
                if isinstance(cmd_reg, dict):
                    for name, spec in cmd_reg.items():
                        if not isinstance(name, str):
                            continue
                        if not isinstance(spec, dict):
                            continue
                        argv = spec.get("argv")
                        if not (isinstance(argv, list) and all(isinstance(x, str) for x in argv)):
                            continue
                        timeout = spec.get("timeout_seconds")
                        if timeout is not None and not isinstance(timeout, (int, float)):
                            timeout = None
                        desc = spec.get("description") if isinstance(spec.get("description"), str) else ""
                        kind = spec.get("kind", "print")
                        if kind not in {"print", "mutate"}:
                            kind = "print"
                        cfg["COMMAND_REGISTER"][name] = {
                            "argv": argv,
                            "timeout_seconds": timeout,
                            "description": desc,
                            "kind": kind,
                        }
        except Exception:
            pass

    return cfg
