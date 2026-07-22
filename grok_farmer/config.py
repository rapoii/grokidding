"""Config loader for Grokidding."""
import json
import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_DIR / "config.json"


def load_config(path=None):
    p = Path(path) if path else CONFIG_PATH
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {p}")
    with open(p, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    # Ensure output dirs exist
    for key in ("accounts_dir", "logs_dir"):
        d = cfg.get("output", {}).get(key, "")
        if d:
            Path(PROJECT_DIR / d).mkdir(parents=True, exist_ok=True)
    return cfg


def get_email_config(cfg):
    return cfg["email"]


def get_proxy_pool(cfg):
    return cfg["proxy"]["pool"]


def get_proxy_mode(cfg):
    return cfg["proxy"].get("mode", "socks5")


def get_ninrouter_config(cfg):
    return cfg["ninrouter"]


def get_turnstile_config(cfg):
    return cfg["turnstile"]


def get_signup_config(cfg):
    return cfg["signup"]
