#!/usr/bin/env python3
"""Stable Cron script: Grok Token Auto-Refresh using curl_cffi."""
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone

import os
from pathlib import Path

CLIENT_ID = "b1a00492-073a-47ea-816f-4c329264a828"
TOKEN_URL = "https://auth.x.ai/oauth2/token"
GROK_SHELL_UA = "grok-shell/0.2.99 (linux; x86_64)"

def _get_router_db() -> Path:
    try:
        from grok_farmer.config import load_config
        cfg = load_config()
        db_path = cfg.get("ninrouter", {}).get("db_path", "")
        if db_path:
            p = Path(db_path)
            if p.exists():
                return p
    except Exception:
        pass

    # Common fallback paths based on active user environment
    appdata = os.environ.get("APPDATA")
    candidates = []
    if appdata:
        candidates.append(Path(appdata) / "9Router" / "db" / "data.sqlite")
        candidates.append(Path(appdata) / "9router" / "db" / "data.sqlite")
    candidates.extend([
        Path.home() / "AppData" / "Roaming" / "9Router" / "db" / "data.sqlite",
        Path.home() / "AppData" / "Roaming" / "9router" / "db" / "data.sqlite",
        Path.home() / ".9router" / "db" / "data.sqlite",
        Path("data.sqlite"),
    ])

    for fallback in candidates:
        if fallback.exists():
            return fallback
    return candidates[0] if candidates else Path("data.sqlite")


def _get_router_db_path() -> str:
    return str(_get_router_db())


def main() -> int:
    # Use curl_cffi to bypass xAI plain requests block
    try:
        from curl_cffi import requests as curl_requests  # type: ignore

        s = curl_requests.Session(impersonate="chrome131")
        print("Using curl_cffi chrome131 impersonation for token refresh.")
    except ImportError:
        print("Error: curl_cffi not installed. Cannot refresh token reliably.")
        return 1

    s.headers.update({"User-Agent": GROK_SHELL_UA, "Accept": "application/json"})

    db_path = _get_router_db()
    if not db_path.exists():
        print(f"9Router DB not found at: {db_path}")
        return 1

    try:
        db = sqlite3.connect(str(db_path))
    except Exception as e:
        print(f"DB open failed: {e}")
        return 1
    db.row_factory = sqlite3.Row
    try:
        rows = db.execute(
            "SELECT id, name, email, data FROM providerConnections WHERE provider = 'grok-cli' AND isActive = 1"
        ).fetchall()
    except Exception as e:
        print(f"DB query failed: {e}")
        db.close()
        return 1

    if not rows:
        print("No active grok-cli connections found.")
        db.close()
        return 0

    stats = {"total": len(rows), "refreshed": 0, "skipped": 0, "failed": 0, "no_refresh": 0}

    for row in rows:
        conn_id = row["id"]
        data = json.loads(row["data"]) if row["data"] else {}
        rt = data.get("refreshToken", "")
        expires_at = data.get("expiresAt", "")

        if not rt:
            stats["no_refresh"] += 1
            continue

        # Check if expired or about to expire (within 1 hour buffer)
        expired = True
        if expires_at:
            try:
                exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                expired = (exp_dt - datetime.now(timezone.utc)).total_seconds() < 3600
            except Exception:
                expired = True

        if not expired:
            stats["skipped"] += 1
            continue

        # Refresh
        try:
            payload = {
                "grant_type": "refresh_token",
                "refresh_token": rt,
                "client_id": CLIENT_ID,
            }
            headers = {"Content-Type": "application/x-www-form-urlencoded"}

            resp = s.post(TOKEN_URL, data=payload, headers=headers, timeout=30)

            if resp.status_code == 200:
                body = resp.json()
                new_at = body.get("access_token", "")
                new_rt = body.get("refresh_token", rt)
                new_exp = body.get("expires_in", 21600)

                if new_at:
                    now = datetime.now(timezone.utc)
                    new_expires_at = datetime.fromtimestamp(
                        now.timestamp() + new_exp, tz=timezone.utc
                    ).isoformat().replace("+00:00", "Z")
                    data["accessToken"] = new_at
                    data["refreshToken"] = new_rt
                    data["expiresAt"] = new_expires_at
                    data["expiresIn"] = new_exp
                    data.pop("lastError", None)
                    data.pop("errorCode", None)
                    data.pop("lastErrorAt", None)
                    data["backoffLevel"] = 0
                    data["testStatus"] = "active"
                    db.execute(
                        "UPDATE providerConnections SET data = ?, updatedAt = ? WHERE id = ?",
                        (json.dumps(data), now.isoformat(), conn_id),
                    )
                    stats["refreshed"] += 1
                else:
                    stats["failed"] += 1
            else:
                stats["failed"] += 1
        except Exception:
            stats["failed"] += 1
        time.sleep(0.5)

    db.commit()
    db.close()

    msg = "🔄 Grok Token Refresh (cron)\n"
    msg += f"Total: {stats['total']} | Refreshed: {stats['refreshed']} | Skipped: {stats['skipped']} | Failed: {stats['failed']}"
    if stats["no_refresh"]:
        msg += f" | No RT: {stats['no_refresh']}"
    if stats["refreshed"] > 0:
        msg += f"\n✅ {stats['refreshed']} token(s) berhasil di-refresh!"
    if stats["failed"] > 0:
        msg += "\n❌ {0} token(s) gagal — mungkin refresh token expired juga".format(stats["failed"])
    if stats["refreshed"] == 0 and stats["failed"] == 0 and stats["skipped"] > 0:
        msg += "\n✅ Semua token masih valid, tidak perlu refresh"
    print(msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
