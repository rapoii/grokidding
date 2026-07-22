"""xAI OAuth Device Code flow.

Flow:
  1. POST auth.x.ai/oauth2/device/code -> user_code + device_code
  2. User visits verification_uri + authorizes
  3. POST auth.x.ai/oauth2/token (poll) -> access_token + refresh_token

Based on 9Router source: open-sse/providers/registry/grok-cli.js
"""
import time
from typing import Optional

CLIENT_ID = "b1a00492-073a-47ea-816f-4c329264a828"
DEVICE_CODE_URL = "https://auth.x.ai/oauth2/device/code"
TOKEN_URL = "https://auth.x.ai/oauth2/token"
SCOPE = "openid profile email offline_access grok-cli:access api:access conversations:read conversations:write"


class OAuthClient:
    def __init__(self, proxy: Optional[str] = None, debug: bool = False, timeout: float = 30.0):
        self.debug = debug
        self.timeout = timeout
        self._proxy = proxy
        self._session = None
        self._init_transport()

    def _init_transport(self):
        from curl_cffi import requests as curl_requests
        self._session = curl_requests.Session(impersonate="chrome131")
        if self._proxy:
            self._session.proxies = {"http": self._proxy, "https": self._proxy}

    def request_device_code(self) -> dict:
        """Request device code from xAI OAuth.

        Returns: {user_code, device_code, verification_uri, interval, expires_in}
        """
        data = {
            "client_id": CLIENT_ID,
            "scope": SCOPE,
        }
        resp = self._session.post(
            DEVICE_CODE_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}: {resp.text[:300]}"}

        result = resp.json()
        if self.debug:
            print(f"  [device_code] user_code={result.get('user_code')}")
        return result

    def poll_token(self, device_code: str, interval: int = 5, timeout: int = 120) -> dict:
        """Poll for OAuth token after device code approval.

        Returns: {access_token, refresh_token, id_token, expires_in, scope}
        """
        deadline = time.time() + timeout
        wait = interval

        while time.time() < deadline:
            data = {
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_code,
                "client_id": CLIENT_ID,
            }
            resp = self._session.post(
                TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self.timeout,
            )

            if resp.status_code == 200:
                result = resp.json()
                if self.debug:
                    print(f"  [poll_token] GOT TOKEN! expires_in={result.get('expires_in')}")
                return result

            body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            error = body.get("error", "")

            if error == "authorization_pending":
                time.sleep(wait)
                continue
            elif error == "slow_down":
                wait += 2
                time.sleep(wait)
                continue
            elif error == "expired_token":
                return {"error": "Device code expired"}
            elif error == "access_denied":
                return {"error": "User denied authorization"}
            else:
                return {"error": f"HTTP {resp.status_code}: {error}"}

        return {"error": "Polling timed out"}

    def refresh_token(self, refresh_token: str) -> dict:
        """Refresh an expired access token."""
        data = {
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "refresh_token": refresh_token,
        }
        resp = self._session.post(
            TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            return {"error": f"Refresh failed: HTTP {resp.status_code}"}
        result = resp.json()
        # Keep original refresh_token if not in response
        if "refresh_token" not in result:
            result["refresh_token"] = refresh_token
        return result
