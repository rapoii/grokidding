"""Auto-refresh expired xAI OAuth tokens for 9Router Grok CLI connections.

Reads all grok-cli connections from 9Router SQLite, finds expired ones
(has refreshToken), refreshes via xAI OAuth, and updates the database.

Usage:
  -m grok_farmer.token_refresher          # Refresh all expired
  -m grok_farmer.token_refresher --dry-run # Check only, don't update
  -m grok_farmer.token_refresher --force   # Refresh all (even non-expired)
"""

import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from typing import Optional

import requests

CLIENT_ID = "b1a00492-073a-47ea-816f-4c329264a828"
TOKEN_URL = "https://auth.x.ai/oauth2/token"
GROK_SHELL_UA = "grok-shell/0.2.99 (linux; x86_64)"


def is_token_expired(expires_at: str, buffer_seconds: int = 300) -> bool:
    """Check if token is expired (or about to expire within buffer)."""
    if not expires_at:
        return True  # No expiry = assume expired
    try:
        # Handle both ISO formats
        exp = expires_at.replace("Z", "+00:00")
        exp_dt = datetime.fromisoformat(exp)
        now = datetime.now(timezone.utc)
        return (exp_dt - now).total_seconds() < buffer_seconds
    except Exception:
        return True


def refresh_access_token(refresh_token: str, timeout: int = 30) -> dict:
    """Refresh an expired access token via xAI OAuth.

    Returns: {access_token, refresh_token, expires_in, id_token, ...}
    or {error: "..."} on failure.
    """
    s = requests.Session()
    s.headers.update({
        "User-Agent": GROK_SHELL_UA,
        "Accept": "application/json",
    })

    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
    }

    try:
        resp = s.post(
            TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=timeout,
        )

        if resp.status_code == 200:
            body = resp.json()
            if "access_token" in body:
                return body
            return {"error": f"No access_token in response: {body}"}

        try:
            body = resp.json()
        except Exception:
            body = {"raw": resp.text[:300]}

        return {"error": f"HTTP {resp.status_code}: {body}"}

    except Exception as e:
        return {"error": str(e)}


def refresh_all_connections(
    db_path: str,
    dry_run: bool = False,
    force: bool = False,
    debug: bool = True,
) -> dict:
    """Refresh all grok-cli connections that have refresh tokens.

    Args:
        db_path: Path to 9Router SQLite database
        dry_run: If True, only check status without refreshing
        force: If True, refresh even non-expired tokens
        debug: Print progress

    Returns: {total, has_refresh, refreshed, failed, skipped, errors}
    """
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    rows = db.execute(
        "SELECT id, name, email, data FROM providerConnections WHERE provider = 'grok-cli' AND isActive = 1"
    ).fetchall()

    stats = {
        "total": len(rows),
        "has_refresh": 0,
        "no_refresh": 0,
        "refreshed": 0,
        "failed": 0,
        "skipped": 0,
        "errors": [],
    }

    if debug:
        print(f"Found {len(rows)} active grok-cli connections")

    for row in rows:
        conn_id = row["id"]
        conn_name = row["name"] or row["email"] or conn_id[:12]
        data = json.loads(row["data"]) if row["data"] else {}

        refresh_token = data.get("refreshToken", "")
        access_token = data.get("accessToken", "")
        expires_at = data.get("expiresAt", "")

        if not refresh_token:
            stats["no_refresh"] += 1
            if debug:
                print(f"  SKIP {conn_name}: no refresh token")
            continue

        stats["has_refresh"] += 1

        expired = is_token_expired(expires_at)
        if not expired and not force:
            stats["skipped"] += 1
            if debug:
                print(f"  SKIP {conn_name}: token still valid (expires {expires_at})")
            continue

        if dry_run:
            status = "EXPIRED" if expired else "VALID"
            if debug:
                print(f"  DRY {conn_name}: {status}, would refresh")
            continue

        # Actually refresh
        if debug:
            print(f"  REFRESHING {conn_name}...", end=" ")

        result = refresh_access_token(refresh_token)

        if "error" in result:
            stats["failed"] += 1
            stats["errors"].append({"id": conn_id, "error": result["error"]})
            if debug:
                print(f"FAILED: {result['error'][:80]}")
            continue

        # Update database
        new_access = result.get("access_token", "")
        new_refresh = result.get("refresh_token", refresh_token)
        new_expires_in = result.get("expires_in", 21600)

        if not new_access:
            stats["failed"] += 1
            stats["errors"].append({"id": conn_id, "error": "No access_token in refresh response"})
            if debug:
                print("FAILED: no access_token")
            continue

        now = datetime.now(timezone.utc)
        new_expires_at = datetime.fromtimestamp(
            now.timestamp() + new_expires_in, tz=timezone.utc
        ).isoformat().replace("+00:00", "Z")

        data["accessToken"] = new_access
        data["refreshToken"] = new_refresh
        data["expiresAt"] = new_expires_at
        data["expiresIn"] = new_expires_in

        # Clear error state
        data.pop("lastError", None)
        data.pop("errorCode", None)
        data.pop("lastErrorAt", None)
        data["backoffLevel"] = 0
        data["testStatus"] = "active"

        db.execute(
            "UPDATE providerConnections SET data = ?, updatedAt = ? WHERE id = ?",
            (json.dumps(data), now.isoformat(), conn_id)
        )

        stats["refreshed"] += 1
        if debug:
            print(f"OK (token len={len(new_access)}, expires {new_expires_at})")

        # Rate limit: don't hammer xAI
        time.sleep(0.5)

    db.commit()
    db.close()

    return stats


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Refresh expired Grok CLI tokens")
    parser.add_argument("--db", default=r"C:\Users\Rafi\AppData\Roaming\9Router\db\data.sqlite")
    parser.add_argument("--dry-run", action="store_true", help="Check only, don't refresh")
    parser.add_argument("--force", action="store_true", help="Refresh all (even valid)")
    parser.add_argument("--quiet", action="store_true", help="Less output")
    args = parser.parse_args()

    print("=" * 60)
    print("  Grok Token Refresher")
    print("=" * 60)

    stats = refresh_all_connections(
        db_path=args.db,
        dry_run=args.dry_run,
        force=args.force,
        debug=not args.quiet,
    )

    print()
    print("=" * 60)
    print(f"  Total connections: {stats['total']}")
    print(f"  Has refresh token: {stats['has_refresh']}")
    print(f"  No refresh token:  {stats['no_refresh']}")
    if args.dry_run:
        print(f"  (DRY RUN — nothing changed)")
    else:
        print(f"  Refreshed: {stats['refreshed']}")
        print(f"  Failed:    {stats['failed']}")
        print(f"  Skipped:   {stats['skipped']}")
    print("=" * 60)

    if stats["errors"]:
        print("\nErrors:")
        for e in stats["errors"]:
            print(f"  {e['id'][:12]}: {e['error'][:100]}")

    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
