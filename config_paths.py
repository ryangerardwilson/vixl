import os

HOME = os.path.expanduser("~")
CONFIG_DIR = os.path.join(HOME, ".config", "vixl")
HISTORY_PATH = os.path.join(CONFIG_DIR, "history.log")
EXTENSIONS_DIR = os.path.join(CONFIG_DIR, "extensions")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.py")

# default settings
AUTO_COMMIT_DEFAULT = False


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
    }
    if os.path.exists(CONFIG_FILE):
        try:
            ns = {}
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                code = f.read()
            exec(compile(code, CONFIG_FILE, "exec"), ns, ns)
            if "AUTO_COMMIT" in ns:
                cfg["AUTO_COMMIT"] = bool(ns["AUTO_COMMIT"])
        except Exception:
            pass
    return cfg

# Example config.py the user can create:
# AUTO_COMMIT = True
