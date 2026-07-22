"""xAI Account Signup via gRPC-Web protocol.

Based on: dongguatanglinux/grok-build-auth/xconsole_client/client.py

Flow:
  1. visit_home() -> GET grok.com (cookies)
  2. load_signup_page() -> scrape Next.js action ID
  3. send_email_code() -> gRPC-Web CreateEmailValidationCode
  4. verify_email_code() -> gRPC-Web VerifyEmailValidationCode
  5. create_account() -> Next.js Server Action

Requires: curl_cffi for TLS fingerprint (chrome131).
"""
import gzip
import http.cookiejar
import io
import json
import re
import time
from typing import Dict, List, Optional, Tuple

from .grpc_web import encode_message, frame_request, parse_response

# xAI account endpoints
ACCOUNTS_ORIGIN = "https://accounts.x.ai"
SIGNUP_URL = f"{ACCOUNTS_ORIGIN}/sign-up?redirect=grok-com&return_to=%2F"
HOME_URL = "https://grok.com/"
GRPC_URL = f"{ACCOUNTS_ORIGIN}/auth_mgmt.AuthManagement"

# gRPC-Web headers
CONNECT_ES_VERSION = "connect-es/2.1.1"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
ACCEPT_LANGUAGE = "en-US,en;q=0.9"
SEC_CH_UA = '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"'
SEC_CH_UA_PLATFORM = '"Windows"'


class SignupClient:
    def __init__(self, proxy: Optional[str] = None, debug: bool = False, timeout: float = 30.0):
        self.debug = debug
        self.timeout = timeout
        self._proxy = proxy
        self._session = None
        self._cookies = http.cookiejar.CookieJar()
        self._next_action_id = None
        self._next_router_state_tree = None
        self._init_transport()

    def _init_transport(self):
        """Initialize curl_cffi session with TLS fingerprint."""
        try:
            from curl_cffi import requests as curl_requests
            self._session = curl_requests.Session(impersonate="chrome131")
            if self._proxy:
                self._session.proxies = {"http": self._proxy, "https": self._proxy}
            self._transport = "curl_cffi"
        except ImportError:
            raise ImportError("curl_cffi required. Install: pip install curl_cffi")

    def _base_headers(self) -> dict:
        return {
            "user-agent": USER_AGENT,
            "accept-language": ACCEPT_LANGUAGE,
            "sec-ch-ua": SEC_CH_UA,
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": SEC_CH_UA_PLATFORM,
        }

    def _grpc_headers(self, referer: str) -> dict:
        h = self._base_headers()
        h.update({
            "content-type": "application/grpc-web+proto",
            "x-grpc-web": "1",
            "x-user-agent": CONNECT_ES_VERSION,
            "accept": "*/*",
            "origin": ACCOUNTS_ORIGIN,
            "referer": referer,
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
        })
        return h

    def visit_home(self) -> int:
        """GET grok.com to establish cookies."""
        h = self._base_headers()
        h.update({
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "sec-fetch-site": "none", "sec-fetch-mode": "navigate",
            "sec-fetch-dest": "document", "upgrade-insecure-requests": "1"
        })
        resp = self._session.get(HOME_URL, headers=h, timeout=self.timeout)
        if self.debug:
            print(f"  [visit_home] status={resp.status_code}, cookies={len(self._session.cookies)}")
        return resp.status_code

    def load_signup_page(self) -> int:
        """GET signup page and scrape Next.js action ID + router state tree."""
        h = self._base_headers()
        h.update({
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "sec-fetch-site": "same-site", "sec-fetch-mode": "navigate",
            "sec-fetch-dest": "document", "referer": "https://console.x.ai/"
        })
        resp = self._session.get(SIGNUP_URL, headers=h, timeout=self.timeout)
        html = resp.text

        # Scrape dynamic action ID from JS chunks
        # Look for patterns like: "XXXX":"action_id"
        action_match = re.search(r'"([0-9a-f]{20,})",\s*"[^"]*sign', html)
        if not action_match:
            # Fallback: look in RSC payload
            action_match = re.search(r'"([0-9a-f]{20,})"', html)
        if action_match:
            self._next_action_id = action_match.group(1)

        # Scrape router state tree
        tree_match = re.search(r'"next-router-state-tree"\s*:\s*"([^"]*)"', html)
        if not tree_match:
            tree_match = re.search(r"next-router-state-tree.*?%5B%22(.*?)%22%5D", html)
        if tree_match:
            self._next_router_state_tree = tree_match.group(1)

        if self.debug:
            print(f"  [load_signup] status={resp.status_code}, action_id={self._next_action_id is not None}")

        return resp.status_code

    def send_email_code(self, email: str) -> dict:
        """gRPC-Web CreateEmailValidationCode — sends OTP to email."""
        referer = SIGNUP_URL
        url = f"{GRPC_URL}/auth_mgmt.AuthManagement/CreateEmailValidationCode"

        # Build protobuf message: field 1 = email
        msg = encode_message([(1, email)])
        framed = frame_request(msg)

        # Base64 encode for grpc-web-text+proto
        import base64
        body_b64 = base64.b64encode(framed).decode("ascii")

        h = self._grpc_headers(referer)
        h["content-type"] = "application/grpc-web-text+proto"

        resp = self._session.post(url, content=body_b64, headers=h, timeout=self.timeout)

        result = {"status": resp.status_code, "grpc_status": None}
        try:
            # Decode base64 response
            resp_bytes = base64.b64decode(resp.text)
            parsed = parse_response(resp_bytes)
            result["grpc_status"] = parsed.get("grpc_status")
            result["messages"] = parsed.get("messages")
        except Exception:
            result["raw"] = resp.text[:500]

        if self.debug:
            print(f"  [send_email_code] status={resp.status_code}, grpc={result.get('grpc_status')}")

        return result

    def verify_email_code(self, email: str, code: str) -> dict:
        """gRPC-Web VerifyEmailValidationCode."""
        referer = SIGNUP_URL
        url = f"{GRPC_URL}/auth_mgmt.AuthManagement/VerifyEmailValidationCode"

        # Build protobuf: field 1 = email, field 2 = code
        msg = encode_message([(1, email), (2, code)])
        framed = frame_request(msg)

        import base64
        body_b64 = base64.b64encode(framed).decode("ascii")

        h = self._grpc_headers(referer)
        h["content-type"] = "application/grpc-web-text+proto"

        resp = self._session.post(url, content=body_b64, headers=h, timeout=self.timeout)

        result = {"status": resp.status_code, "grpc_status": None}
        try:
            resp_bytes = base64.b64decode(resp.text)
            parsed = parse_response(resp_bytes)
            result["grpc_status"] = parsed.get("grpc_status")
            result["messages"] = parsed.get("messages")
        except Exception:
            result["raw"] = resp.text[:500]

        if self.debug:
            print(f"  [verify_email_code] status={resp.status_code}, grpc={result.get('grpc_status')}")

        return result

    def create_account(self, email: str, password: str, given_name: str,
                       email_validation_code: str, turnstile_token: str,
                       castle_request_token: str = "", conversion_id: str = "") -> dict:
        """Create account via Next.js Server Action.

        This is the final step — combines all collected tokens.
        """
        if not self._next_action_id:
            return {"error": "No action ID scraped. Call load_signup_page() first."}

        import base64
        import secrets

        if not conversion_id:
            conversion_id = secrets.token_hex(16)

        # Build form data for Next.js Server Action
        form_data = {
            "1_email": email,
            "1_givenName": given_name,
            "1_familyName": "",
            "1_password": password,
            "1_emailValidationCode": email_validation_code,
            "1_turnstileToken": turnstile_token,
            "1_castleRequestToken": castle_request_token,
            "1_conversionId": conversion_id,
        }

        h = self._base_headers()
        h.update({
            "accept": "text/x-component",
            "content-type": "multipart/form-data; boundary=----formdata",
            "next-action": self._next_action_id,
            "next-router-state-tree": self._next_router_state_tree or "",
            "referer": SIGNUP_URL,
            "origin": ACCOUNTS_ORIGIN,
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
        })

        # Build multipart body
        boundary = "----formdata"
        parts = []
        for key, val in form_data.items():
            parts.append(f"--{boundary}\r\n")
            parts.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n')
            parts.append(f"{val}\r\n")
        parts.append(f"--{boundary}--\r\n")
        body = "".join(parts).encode("utf-8")

        resp = self._session.post(SIGNUP_URL, content=body, headers=h, timeout=self.timeout)

        result = {
            "status": resp.status_code,
            "success": False,
            "cookies": dict(self._session.cookies),
        }

        # Check for success indicators
        if resp.status_code in (200, 303):
            result["success"] = True
            # Look for session tokens in response
            if "auth_token" in str(self._session.cookies):
                result["has_session"] = True

        if self.debug:
            print(f"  [create_account] status={resp.status_code}, success={result['success']}")

        return result
