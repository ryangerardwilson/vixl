import os

HOME = os.path.expanduser("~")
CONFIG_DIR = os.path.join(HOME, ".config", "vixl")
HISTORY_PATH = os.path.join(CONFIG_DIR, "history.log")
EXTENSIONS_DIR = os.path.join(CONFIG_DIR, "extensions")
CONFIG_JSON = os.path.join(CONFIG_DIR, "config.json")

# default settings
AUTO_COMMIT_DEFAULT = False
TAB_FUZZY_EXPANSIONS_REGISTER_DEFAULT = []


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
        "AUTO_COMMIT": AUTO_COMMIT_DEFAULT,
        "TAB_FUZZY_EXPANSIONS_REGISTER": list(TAB_FUZZY_EXPANSIONS_REGISTER_DEFAULT),
    }

    if os.path.exists(CONFIG_JSON):
        try:
            import json

            with open(CONFIG_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                if "AUTO_COMMIT" in data:
                    cfg["AUTO_COMMIT"] = bool(data["AUTO_COMMIT"])
                cmd_mode = data.get("cmd_mode")
                reg = (
                    cmd_mode.get("tab_fuzzy_expansions_register")
                    if isinstance(cmd_mode, dict)
                    else None
                )
                if isinstance(reg, list):
                    cfg["TAB_FUZZY_EXPANSIONS_REGISTER"] = [
                        str(item) for item in reg if isinstance(item, str)
                    ]
        except Exception:
            pass

    return cfg

