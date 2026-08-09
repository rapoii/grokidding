"""xAI OAuth Device Code flow.

Flow:
  1. GET 9Router /api/oauth/grok-cli/device-code -> user_code + device_code + codeVerifier
  2. User visits consent page + authorizes (browser)
  3. POST auth.x.ai/oauth2/token (direct poll, bypass 9Router) -> access_token + refresh_token

CRITICAL: xAI requires PKCE code_verifier for device code token exchange,
but xAI's own /device/code endpoint does NOT return codeVerifier.
9Router generates codeVerifier and returns it — so we MUST use 9Router
for step 1, then poll xAI directly for step 3 (9Router's poll is broken).

User-Agent MUST be grok-shell/0.2.99 (not Chrome).
"""
import time
import requests
from typing import Optional

CLIENT_ID = "b1a00492-073a-47ea-816f-4c329264a828"
TOKEN_URL = "https://auth.x.ai/oauth2/token"
GROK_SHELL_UA = "grok-shell/0.2.99 (linux; x86_64)"


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
        s = requests.Session()
        s.headers.update({
            "User-Agent": GROK_SHELL_UA,
            "Accept": "application/json",
        })
        if self._proxy:
            s.proxies = {"http": self._proxy, "https": self._proxy}
        return s

    def _make_router_session(self):
        s = requests.Session()
        s.verify = False
        s.post(
            f"{self.router_url}/api/auth/login",
            json={"password": self.router_password},
            timeout=self.timeout,
        )
        return s

    def request_device_code(self) -> dict:
        """Request device code via 9Router (returns codeVerifier for PKCE).

        Returns: {user_code, device_code, verification_uri, codeVerifier, interval, expires_in}
        """
        resp = self._router_session.get(
            f"{self.router_url}/api/oauth/grok-cli/device-code",
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            return {"error": f"Device code request failed: {resp.status_code} {resp.text[:200]}"}
        result = resp.json()
        if self.debug:
            print(f"  [oauth] device_code OK, user_code={result.get('user_code')}")
        return result

    def poll_token(self, device_code: str, code_verifier: str = "",
                   interval: int = 5, timeout: int = 180,
                   stop_event=None) -> dict:
        """Poll xAI directly for access token (bypass 9Router poll).

        CRITICAL: code_verifier from 9Router's device-code response is REQUIRED.
        Without it, xAI returns invalid_grant.

        Returns: {access_token, refresh_token, expires_in, id_token, ...}
        """
        data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": device_code,
            "client_id": CLIENT_ID,
            "code_verifier": code_verifier,
        }
        start = time.time()
        while time.time() - start < timeout:
            if stop_event and stop_event.is_set():
                return {"error": "cancelled"}
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
                # Sleep in small chunks so stop_event can interrupt
                slept = 0
                while slept < wait:
                    if stop_event and stop_event.is_set():
                        return {"error": "cancelled"}
                    time.sleep(min(1, wait - slept))
                    slept += 1
                continue

            # Terminal errors
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
