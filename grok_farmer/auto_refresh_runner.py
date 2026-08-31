#!/usr/bin/env python3
"""Wrapper + check for Grokidding auto token refresher."""
import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_DIR / "config.json"

def should_run() -> bool:
    if not CONFIG_PATH.exists():
        return True
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return cfg.get("auto_refresh", True) is True
    except Exception:
        return True

if __name__ == "__main__":
    if not should_run():
        print("[Auto-Refresh] Disabled in config.json (auto_refresh=false) — skipping.")
        sys.exit(0)
    # Import and run the real refresher. It has its own main guard now.
    from grok_farmer.cron_token_refresher import main
    main()
