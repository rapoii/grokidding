"""Push OAuth tokens to 9Router as Grok CLI connections.

Two methods:
  1. API: POST /api/oauth/grok-cli/exchange (JWT passthrough)
  2. SQLite: INSERT into providerConnections
"""
import json
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from typing import Optional


class RouterPusher:
    def __init__(self, base_url: str, password: str, db_path: Optional[str] = None,
                 debug: bool = False):
        self.base_url = base_url.rstrip("/")
        self.password = password
        self.db_path = db_path
        self.debug = debug
        self._session = None
        self._cookie = None

    def _init_transport(self):
        from curl_cffi import requests as curl_requests
        self._session = curl_requests.Session(impersonate="chrome131")

    def login(self, retries=3) -> bool:
        """Login to 9Router dashboard and get auth cookie. Retries on DNS errors."""
        if not self._session:
            self._init_transport()
        for attempt in range(retries):
            try:
                resp = self._session.post(
                    f"{self.base_url}/api/auth/login",
                    json={"password": self.password},
                    timeout=15,
                )
                if resp.status_code == 200:
                    cookies = dict(self._session.cookies)
                    self._cookie = cookies.get("auth_token", "")
                    if self.debug:
                        print(f"  [9router login] OK, cookie={self._cookie[:20]}...")
                    return bool(self._cookie)
                if self.debug:
                    print(f"  [9router login] FAIL: {resp.status_code}")
                return False
            except Exception as e:
                if self.debug:
                    print(f"  [9router login] attempt {attempt+1}/{retries}: {e}")
                if attempt < retries - 1:
                    import time
                    time.sleep(2 * (attempt + 1))
        return False

    def push_via_api(self, access_token: str) -> dict:
        """Push token via API exchange endpoint.

        The exchange endpoint accepts JWT access tokens directly
        and creates a new connection automatically.
        """
        if not self._cookie:
            if not self.login():
                return {"error": "Login failed"}

        resp = self._session.post(
            f"{self.base_url}/api/oauth/grok-cli/exchange",
            json={"code": access_token},
            headers={"Cookie": f"auth_token={self._cookie}"},
            timeout=30,
        )

        result = {"status": resp.status_code}
        try:
            data = resp.json()
            result.update(data)
        except Exception:
            result["raw"] = resp.text[:500]

        if self.debug:
            print(f"  [push_api] status={resp.status_code}, success={result.get('success')}")

        # Fix authType: 9Router API sets 'access_token' but frontend expects 'oauth'
        if result.get('success') and self.db_path:
            try:
                db = sqlite3.connect(self.db_path)
                db.execute(
                    "UPDATE providerConnections SET authType = 'oauth' WHERE provider = 'grok-cli' AND authType = 'access_token'"
                )
                db.commit()
                db.close()
                if self.debug:
                    print("  [push_api] Fixed authType to 'oauth'")
            except Exception:
                pass

        return result

    def push_via_sqlite(self, access_token: str, refresh_token: str,
                        email: str, display_name: str,
                        id_token: str = "", user_id: str = "",
                        scope: str = "", expires_in: int = 21600) -> dict:
        """Push token directly to SQLite database.

        This is the fallback method if API doesn't work.
        """
        if not self.db_path:
            return {"error": "No db_path configured"}

        now = datetime.now(timezone.utc)
        expires_at = datetime.fromtimestamp(
            now.timestamp() + expires_in, tz=timezone.utc
        ).isoformat().replace("+00:00", "Z")

        conn_id = str(uuid.uuid4())
        data = {
            "displayName": display_name,
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "expiresAt": expires_at,
            "scope": scope or "openid profile email offline_access grok-cli:access api:access conversations:read conversations:write",
            "testStatus": "active",
            "expiresIn": expires_in,
            "providerSpecificData": {
                "authMethod": "device_code",
                "idToken": id_token,
                "email": email,
                "userId": user_id,
                "hasGrokCodeAccess": True,
                "subscriptionTier": None,
            },
        }

        try:
            db = sqlite3.connect(self.db_path)

            # Ensure grok-cli provider node exists
            existing = db.execute("SELECT id FROM providerNodes WHERE id = 'grok-cli'").fetchone()
            if not existing:
                db.execute(
                    "INSERT INTO providerNodes (id, type, name, data, createdAt, updatedAt) VALUES (?, ?, ?, ?, ?, ?)",
                    ('grok-cli', 'grok-cli', 'Grok CLI',
                     json.dumps({"prefix": "gcli", "apiType": "responses"}),
                     now.isoformat(), now.isoformat())
                )
                db.commit()
                if self.debug:
                    print("  [push_sqlite] Created grok-cli provider node")

            db.execute(
                """INSERT INTO providerConnections
                   (id, provider, authType, name, email, priority, isActive, data, createdAt, updatedAt)
                   VALUES (?, 'grok-cli', 'oauth', ?, ?, ?, 1, ?, ?, ?)""",
                (
                    conn_id,
                    email,
                    email,
                    self._get_next_priority(db),
                    json.dumps(data),
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
            db.commit()
            db.close()

            if self.debug:
                print(f"  [push_sqlite] INSERT OK: {conn_id}")

            return {"success": True, "id": conn_id}

        except Exception as e:
            return {"error": str(e)}

    def _get_next_priority(self, db) -> int:
        """Get next priority number for grok-cli connections."""
        cursor = db.execute(
            "SELECT MAX(priority) FROM providerConnections WHERE provider = 'grok-cli'"
        )
        row = cursor.fetchone()
        return (row[0] or 0) + 1
