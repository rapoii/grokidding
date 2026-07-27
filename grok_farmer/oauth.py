"""xAI OAuth Device Code flow.

Flow:
  1. POST auth.x.ai/oauth2/device/code -> user_code + device_code
  2. User visits consent page + authorizes (browser)
  3. POST auth.x.ai/oauth2/token (poll) -> access_token + refresh_token

CRITICAL: MUST use curl_cffi with impersonate="chrome131" for all xAI API calls.
Plain requests library causes xAI to require code_verifier (PKCE) which
xAI's device code endpoint does NOT return. curl_cffi Chrome fingerprint
bypasses this requirement.

Based on proven working code (aea98a1) + verified 2026-07-27.
"""
import time
from typing import Optional

CLIENT_ID = "b1a00492-073a-47ea-816f-4c329264a828"
DEVICE_CODE_URL = "https://auth.x.ai/oauth2/device/code"
TOKEN_URL = "https://auth.x.ai/oauth2/token"
SCOPE = "openid profile email offline_access grok-cli:access api:access conversations:read conversations:write"


class OAuthClient:
    def __init__(
        self,
        router_url: str = "http://localhost:20128",
        router_password: str = "rafi12345",
        proxy: Optional[str] = None,
        timeout: int = 30,
        debug: bool = False,
    ):
        self.router_url = router_url.rstrip("/")
        self.router_password = router_password
        self._proxy = proxy
        self.timeout = timeout
        self.debug = debug
        self._session = self._make_session()
        self._router_session = self._make_router_session()

    def _make_session(self):
        from curl_cffi import requests as curl_requests
        s = curl_requests.Session(impersonate="chrome131")
        if self._proxy:
            s.proxies = {"http": self._proxy, "https": self._proxy}
        return s

    def _make_router_session(self):
        import requests
        s = requests.Session()
        s.verify = False
        s.post(
            f"{self.router_url}/api/auth/login",
            json={"password": self.router_password},
            timeout=self.timeout,
        )
        return s

    def request_device_code(self) -> dict:
        """Request device code from xAI directly (no 9Router, no codeVerifier needed).

        Returns: {user_code, device_code, verification_uri, interval, expires_in}
        """
        data = {"client_id": CLIENT_ID, "scope": SCOPE}
        resp = self._session.post(
            DEVICE_CODE_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        result = resp.json()
        if self.debug:
            print(f"  [oauth] device_code OK, user_code={result.get('user_code')}")
        return result

    def poll_token(self, device_code: str, interval: int = 5, timeout: int = 300) -> dict:
        """Poll xAI directly for access token. No code_verifier needed (curl_cffi).

        Returns: {access_token, refresh_token, expires_in, id_token, ...}
        """
        data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": device_code,
            "client_id": CLIENT_ID,
        }
        start = time.time()
        while time.time() - start < timeout:
            resp = self._session.post(
                TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self.timeout,
            )
            body = {}
            try:
                body = resp.json()
            except Exception:
                body = {"raw": resp.text[:300]}

            if resp.status_code == 200 and "access_token" in body:
                if self.debug:
                    print(f"  [oauth] token OK, access_token len={len(body['access_token'])}")
                return body

            error = body.get("error", "")
            if error in ("authorization_pending", "slow_down"):
                wait = interval
                if error == "slow_down":
                    wait = max(interval, int(body.get("interval", interval)) + 2)
                if self.debug:
                    print(f"  [oauth] {error}, wait {wait}s...")
                time.sleep(wait)
                continue

            if self.debug:
                print(f"  [oauth] poll error: {error or resp.status_code} {str(body)[:200]}")
            return {"error": error or f"HTTP {resp.status_code}", "detail": body}

        return {"error": "timeout", "detail": f"No token after {timeout}s"}

    def push_to_router(self, access_token: str) -> dict:
        """Push token to 9Router via exchange API."""
        resp = self._router_session.post(
            f"{self.router_url}/api/oauth/grok-cli/exchange",
            json={"code": access_token},
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            return {"error": f"Push failed: {resp.status_code} {resp.text[:200]}"}
        return resp.json()

    def refresh_token(self, refresh_token: str) -> dict:
        """Refresh an expired access token."""
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": CLIENT_ID,
        }
        resp = self._session.post(
            TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            return {"error": f"Refresh failed: {resp.status_code} {resp.text[:200]}"}
        return resp.json()
