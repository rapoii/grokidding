"""Utility functions for Grokidding."""
import random
import string
import json
import time
from datetime import datetime, timezone
from pathlib import Path


def generate_email(domain: str) -> str:
    """Generate random email address."""
    chars = string.ascii_lowercase + string.digits
    length = random.randint(8, 13)
    local = "".join(random.choice(chars) for _ in range(length))
    return f"{local}@{domain}"


def generate_password(length: int = 16) -> str:
    """Generate strong password."""
    lower = string.ascii_lowercase
    upper = string.ascii_uppercase
    digits = string.digits
    special = "!@#$%"
    pwd = [random.choice(lower), random.choice(upper),
           random.choice(digits), random.choice(special)]
    all_chars = lower + upper + digits + special
    pwd += [random.choice(all_chars) for _ in range(length - 4)]
    random.shuffle(pwd)
    return "".join(pwd)


def generate_name() -> str:
    """Generate random first name."""
    names = [
        "Ahmad", "Budi", "Citra", "Dewi", "Eka", "Fajar", "Gita",
        "Hadi", "Indra", "Joko", "Kartika", "Lestari", "Muhammad",
        "Nina", "Omar", "Putri", "Rizki", "Sari", "Tono", "Umar",
        "Vina", "Wahyu", "Xena", "Yusuf", "Zahra"
    ]
    return random.choice(names)


def generate_uuid() -> str:
    """Generate random UUID."""
    import uuid
    return str(uuid.uuid4())


def save_account(account_data: dict, accounts_dir: str):
    """Save account data to JSON file."""
    d = Path(accounts_dir)
    d.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    email_safe = account_data.get("email", "unknown").replace("@", "_at_")
    path = d / f"grok_{email_safe}_{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(account_data, f, indent=2)
    return path


def log_event(logs_dir: str, event: str, data: dict = None):
    """Append event to log file."""
    d = Path(logs_dir)
    d.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = d / f"run_{ts}.log"
    now = datetime.now(timezone.utc).strftime("%H:%M:%S")
    line = f"[{now}] {event}"
    if data:
        line += f" | {json.dumps(data, default=str)}"
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
