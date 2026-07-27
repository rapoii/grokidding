"""xAI OAuth Authorization Code flow (replaces device code flow).

Flow:
  1. Start local HTTP server on 127.0.0.1:56121/callback
  2. Navigate browser to auth.x.ai/oauth2/authorize (user already logged in)
  3. xAI redirects to localhost with auth code
  4. Exchange code for tokens via curl_cffi

This flow works for NEW accounts because the browser navigates directly
to auth.x.ai — no need for auth.x.ai session cookies. The browser's
existing session (from signup on accounts.x.ai) is used automatically.

Based on 9Router source: xai.js XaiService.connect()
Verified via OpenID discovery: https://auth.x.ai/.well-known/openid-configuration
"""
import time
import hashlib
import base64
import secrets
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional

CLIENT_ID = "b1a00492-073a-47ea-816f-4c329264a828"
AUTHORIZE_URL = "https://auth.x.ai/oauth2/authorize"
TOKEN_URL = "https://auth.x.ai/oauth2/token"
SCOPE = "openid profile email offline_access grok-cli:access api:access conversations:read conversations:write"
REDIRECT_PORT = 56121
REDIRECT_PATH = "/callback"
REDIRECT_URI = f"http://127.0.0.1:{REDIRECT_PORT}{REDIRECT_PATH}"


def _generate_pkce():
    """Generate PKCE code_verifier and code_challenge."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(96)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


class _CallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler that captures OAuth callback params."""
    callback_params = None

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == REDIRECT_PATH:
            params = parse_qs(parsed.query)
            _CallbackHandler.callback_params = {
                k: v[0] if len(v) == 1 else v for k, v in params.items()
            }
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Authorization successful! You can close this tab.</h1>")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress HTTP logs


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
        self._code_verifier = None
        self._state = None

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
        try:
            resp = s.post(
                f"{self.router_url}/api/auth/login",
                json={"password": self.router_password},
                timeout=self.timeout,
            )
            if self.debug:
                print(f"  [oauth] 9Router login: {resp.status_code}")
        except Exception as e:
            if self.debug:
                print(f"  [oauth] 9Router login failed: {e}")
        return s

    def build_auth_url(self) -> str:
        """Build authorization URL for browser redirect.

        Returns URL to navigate the browser to. The user must be logged in.
        After approval, xAI redirects to localhost:56121/callback with auth code.
        """
        self._code_verifier, code_challenge = _generate_pkce()
        self._state = secrets.token_hex(16)
        nonce = secrets.token_hex(16)

        params = {
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPE,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": self._state,
            "nonce": nonce,
            "plan": "generic",
            "referrer": "cli-proxy-api",
        }
        from urllib.parse import urlencode
        qs = urlencode(params)
        url = f"{AUTHORIZE_URL}?{qs}"

        if self.debug:
            print(f"  [oauth] auth_url built, state={self._state[:8]}...")
        return url

    def wait_for_callback(self, timeout: int = 180) -> dict:
        """Start local server and wait for xAI callback.

        Returns: {code, state} or {error: ...}
        Must call build_auth_url() first.
        """
        _CallbackHandler.callback_params = None
        server = HTTPServer(("127.0.0.1", REDIRECT_PORT), _CallbackHandler)
        server.timeout = 1  # Check every 1s

        if self.debug:
            print(f"  [oauth] listening on {REDIRECT_URI}")

        start = time.time()
        while time.time() - start < timeout:
            server.handle_request()
            if _CallbackHandler.callback_params:
                params = _CallbackHandler.callback_params
                server.server_close()
                if params.get("error"):
                    return {"error": params.get("error_description") or params["error"]}
                if params.get("state") != self._state:
                    return {"error": "State mismatch — possible CSRF"}
                if not params.get("code"):
                    return {"error": "No authorization code in callback"}
                if self.debug:
                    print(f"  [oauth] callback received, code={params['code'][:20]}...")
                return params

        server.server_close()
        return {"error": "timeout", "detail": f"No callback after {timeout}s"}

    def exchange_code(self, code: str) -> dict:
        """Exchange authorization code for tokens.

        Returns: {access_token, refresh_token, expires_in, id_token, ...}
        """
        data = {
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": self._code_verifier,
        }
        resp = self._session.post(
            TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            return {"error": f"Token exchange failed: {resp.status_code} {resp.text[:200]}"}
        result = resp.json()
        if self.debug:
            print(f"  [oauth] token OK, access_token len={len(result.get('access_token', ''))}")
        return result

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
